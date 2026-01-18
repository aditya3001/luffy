"""
Celery tasks for asynchronous log processing and analysis.

This module defines background tasks that can be executed asynchronously
using Celery workers. Tasks include:
- Periodic log fetching and processing
- RCA generation for exception clusters
- Code indexing
- Notification sending
"""
import logging
from typing import Dict, Any, List
from datetime import datetime

from celery import Celery
from celery.schedules import crontab

from src.config import settings
from src.ingestion.log_fetcher import LogFetcher
from src.services.processor import LogProcessor
from src.services.llm_analyzer import LLMAnalyzer
from src.services.code_indexer import CodeIndexer
from src.services.clustering import ExceptionClusterer
from src.services.task_config import task_config_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Celery app
celery_app = Celery(
    'luffy',
    broker=settings.redis_url,
    backend=settings.redis_url
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# ============================================================================
# PERIODIC TASKS (Scheduled by Celery Beat)
# ============================================================================

@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """
    Configure periodic tasks to run on schedule.
    
    This is called when Celery Beat starts up.
    
    Note: RCA generation and code indexing are now on-demand only (no scheduling).
    They can be triggered manually via API or automatically when needed.
    """
    
    # Task 1: Fetch and process logs every N minutes
    # Uses the flexible duration configuration
    # Note: This respects the log_processing_enabled toggle per service
    interval_minutes = settings.fetch_interval_minutes
    sender.add_periodic_task(
        interval_minutes * 60.0,  # Convert to seconds
        fetch_and_process_logs.s(),
        name=f'fetch-and-process-logs-every-{interval_minutes}m'
    )
    
    # Task 2: Cleanup old data (weekly on Sunday at 3 AM)
    sender.add_periodic_task(
        crontab(hour=3, minute=0, day_of_week=0),
        cleanup_old_data.s(days=30),
        name='cleanup-old-data-weekly'
    )
    
    logger.info("Periodic tasks configured successfully")
    logger.info("Note: RCA and code indexing are on-demand only (no scheduling)")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _validate_log_source_config(log_source, task_id: str) -> bool:
    """
    Validate log source configuration for optimal performance.
    
    Args:
        log_source: LogSource database model
        task_id: Task ID for logging
        
    Returns:
        True if configuration is valid, False otherwise
    """
    issues = []
    
    # Check fetch interval
    if hasattr(log_source, 'fetch_interval_minutes') and log_source.fetch_interval_minutes:
        if log_source.fetch_interval_minutes < 1:
            issues.append(f"Fetch interval too low: {log_source.fetch_interval_minutes}m (minimum: 1m)")
        elif log_source.fetch_interval_minutes > 1440:  # 24 hours
            issues.append(f"Fetch interval too high: {log_source.fetch_interval_minutes}m (maximum: 1440m)")
    
    # Check required fields
    if not log_source.host:
        issues.append("Missing host configuration")
    if not log_source.index_pattern:
        issues.append("Missing index pattern configuration")
    
    # Log issues
    if issues:
        logger.error(f"[Task {task_id}] Log source {log_source.name} configuration issues: {'; '.join(issues)}")
        return False
    
    return True


def _calculate_optimal_fetch_duration(fetch_interval_minutes: int) -> int:
    """
    Calculate optimal log fetch duration to avoid overlap while accounting for skew.
    
    Formula: fetch_duration = fetch_interval + buffer_time + processing_skew
    
    Args:
        fetch_interval_minutes: Scheduled fetch interval in minutes
        
    Returns:
        Optimal fetch duration in minutes
    """
    # Base duration = fetch interval
    base_duration = fetch_interval_minutes
    
    buffer_time = 0.2 #(0.2 minute)
    
    # Processing skew (fixed based on interval)
    if fetch_interval_minutes <= 5:
        processing_skew = 0.2  # 0.2 minutes for high-frequency
    elif fetch_interval_minutes <= 30:
        processing_skew = 1  # 1 minutes for low-frequency
    else:
        processing_skew = 2  # 2 minutes for very low-frequency
    
    optimal_duration = base_duration + buffer_time + processing_skew
    
    logger.info(f"Calculated optimal fetch duration: {optimal_duration}m (interval: {fetch_interval_minutes}m, buffer: {buffer_time}m, skew: {processing_skew}m)")
    
    return optimal_duration


def _should_index_code_for_service(service_id: str) -> bool:
    """
    Determine if code indexing is needed for a service.
    
    Checks:
    1. Is repository configured?
    2. Has code changed since last index? (Git commit SHA)
    3. Is indexing already in progress?
    4. Time since last index (minimum interval to avoid spam)
    
    Args:
        service_id: Service ID to check
        
    Returns:
        True if indexing should be triggered, False otherwise
    """
    from src.storage.database import get_db
    from src.storage.models import Service
    from datetime import timedelta
    
    with get_db() as db:
        service = db.query(Service).filter(Service.id == service_id).first()
        
        if not service or not service.git_repo_path:
            logger.debug(f"Service {service_id} has no Git repository configured")
            return False
        
        if not service.code_indexing_enabled:
            logger.debug(f"Code indexing disabled for service {service_id}")
            return False
        
        # Check if already indexing
        if service.code_indexing_status == 'indexing':
            logger.info(f"Code indexing already in progress for service {service_id}")
            return False
        
        # Check minimum interval (5 minutes to avoid spam)
        if service.last_code_indexing:
            time_since_last = datetime.utcnow() - service.last_code_indexing
            if time_since_last < timedelta(minutes=5):
                logger.debug(f"Code indexed recently for service {service_id}, skipping")
                return False
        
        # Check if code has changed (Git commit SHA)
        try:
            from src.services.code_indexer_factory import CodeIndexerFactory
            
            # Extract service data inside session
            use_api_mode = service.use_api_mode if hasattr(service, 'use_api_mode') else False
            repository_url = service.repository_url
            git_branch = service.git_branch or 'main'
            git_repo_path = service.git_repo_path
            access_token = service.access_token if hasattr(service, 'access_token') else None
            last_indexed_commit = service.last_indexed_commit
            
            # Session closed, now use extracted data
            # Create indexer using factory
            indexer = CodeIndexerFactory.create_from_service(
                service_data={
                    'id': service_id,
                    'use_api_mode': use_api_mode,
                    'repository_url': repository_url,
                    'git_branch': git_branch,
                    'git_repo_path': git_repo_path,
                    'access_token': access_token,
                }
            )
            
            # Get current commit SHA
            current_commit = None
            if hasattr(indexer, 'commit_sha') and indexer.commit_sha:
                # Local mode: commit_sha from local repo
                current_commit = indexer.commit_sha
            elif use_api_mode and hasattr(indexer, 'git_client'):
                # API mode: fetch commit SHA via API
                try:
                    if indexer.git_provider == 'github':
                        current_commit = indexer.git_client.get_latest_commit(
                            indexer.repository_owner,
                            indexer.repository_name,
                            indexer.branch
                        )
                    elif indexer.git_provider == 'gitlab':
                        current_commit = indexer.git_client.get_latest_commit(
                            indexer.project_id,
                            indexer.branch
                        )
                except Exception as api_error:
                    logger.warning(f"Could not fetch commit via API for service {service_id}: {api_error}")
            
            if not current_commit:
                logger.warning(f"Could not determine current commit for service {service_id}, triggering indexing")
                return True
            
            if current_commit == last_indexed_commit:
                logger.info(f"Code unchanged for service {service_id} (commit: {current_commit[:8]})")
                return False
            
            logger.info(f"Code changed for service {service_id}: {last_indexed_commit[:8] if last_indexed_commit else 'never'} -> {current_commit[:8]}")
            return True
            
        except Exception as e:
            logger.error(f"Error checking commit SHA for service {service_id}: {e}")
            # Index anyway if we can't determine (better safe than sorry)
            return True


def _mark_indexing_in_progress(service_id: str):
    """Mark service as currently indexing"""
    from src.storage.database import get_db
    from src.storage.models import Service
    
    with get_db() as db:
        db.query(Service).filter(Service.id == service_id).update({
            'code_indexing_status': 'indexing',
            'updated_at': datetime.utcnow()
        })
        db.commit()
        logger.info(f"Marked service {service_id} as indexing in progress")


def _mark_indexing_complete(service_id: str, commit_sha: str):
    """Mark service indexing as complete"""
    from src.storage.database import get_db
    from src.storage.models import Service
    
    with get_db() as db:
        db.query(Service).filter(Service.id == service_id).update({
            'code_indexing_status': 'completed',
            'last_code_indexing': datetime.utcnow(),
            'last_indexed_commit': commit_sha,
            'code_indexing_error': None,
            'updated_at': datetime.utcnow()
        })
        db.commit()
        logger.info(f"Marked service {service_id} indexing as complete (commit: {commit_sha[:8]})")


def _mark_indexing_failed(service_id: str, error: str):
    """Mark service indexing as failed"""
    from src.storage.database import get_db
    from src.storage.models import Service
    
    with get_db() as db:
        db.query(Service).filter(Service.id == service_id).update({
            'code_indexing_status': 'failed',
            'code_indexing_error': error,
            'updated_at': datetime.utcnow()
        })
        db.commit()
        logger.error(f"Marked service {service_id} indexing as failed: {error}")


# ============================================================================
# ASYNC TASKS
# ============================================================================

@celery_app.task(name='tasks.fetch_and_process_logs', bind=True)
def fetch_and_process_logs(self, service_id: str = None, log_source_id: str = None) -> Dict[str, Any]:
    """
    Fetch logs from configured log sources and process them through the pipeline.
    
    This is the main periodic task that:
    1. Fetches logs from multiple log sources (database-configured)
    2. Processes them through LogProcessor
    3. Extracts exceptions
    4. Clusters similar exceptions
    5. Sends notifications
    6. Triggers RCA generation if needed
    
    Args:
        service_id: Optional service ID to fetch logs for specific service
        log_source_id: Optional log source ID to fetch from specific source
    
    Returns:
        Processing statistics
    """
    task_id = self.request.id
    logger.info(f"[Task {task_id}] Starting log fetch and process")
    
    # Check if task is enabled
    if not task_config_manager.is_task_enabled('fetch_and_process_logs'):
        logger.info(f"[Task {task_id}] Task is disabled, skipping execution")
        return {'status': 'skipped', 'reason': 'task_disabled'}
    
    try:
        from src.storage.database import get_db_dependency
        from src.storage.models import LogSource, Service
        
        # Get database session
        db = next(get_db_dependency())
        
        try:
            # Get log sources to fetch from
            if log_source_id:
                # Fetch from specific log source
                log_sources = db.query(LogSource).filter(
                    LogSource.id == log_source_id,
                    LogSource.is_active == True,
                    LogSource.fetch_enabled == True
                ).all()
            elif service_id:
                # Fetch from all log sources for specific service
                log_sources = db.query(LogSource).filter(
                    LogSource.service_id == service_id,
                    LogSource.is_active == True,
                    LogSource.fetch_enabled == True
                ).all()
            else:
                # Fetch from all enabled log sources (default behavior)
                log_sources = db.query(LogSource).join(Service).filter(
                    LogSource.is_active == True,
                    LogSource.fetch_enabled == True,
                    Service.is_active == True
                ).all()
            
            if not log_sources:
                # No fallback - strict service association required
                error_msg = f"No active log sources found. Service association is required."
                logger.error(f"[Task {task_id}] {error_msg}")
                return {
                    'status': 'error',
                    'task_id': task_id,
                    'error': error_msg,
                    'reason': 'no_log_sources_configured'
                }
            
            logger.info(f"[Task {task_id}] Found {len(log_sources)} log sources to fetch from")
            
            total_logs = 0
            total_stats = {'exceptions_found': 0, 'clusters_created': 0, 'notifications_sent': 0}
            source_results = []
            
            # Fetch from each log source
            for log_source in log_sources:
                try:
                    # Check if log processing is enabled for this service
                    service = db.query(Service).filter(Service.id == log_source.service_id).first()
                    if not service:
                        logger.warning(f"[Task {task_id}] Service {log_source.service_id} not found, skipping")
                        continue
                    
                    if not service.log_processing_enabled:
                        logger.info(f"[Task {task_id}] Log processing disabled for service {service.name}, skipping")
                        source_results.append({
                            'log_source': log_source.name,
                            'status': 'skipped',
                            'reason': 'log_processing_disabled'
                        })
                        continue
                    
                    logger.info(f"[Task {task_id}] Fetching from log source: {log_source.name} ({log_source.source_type})")
                    
                    # Validate log source configuration
                    # if not _validate_log_source_config(log_source, task_id):
                    #     logger.error(f"[Task {task_id}] Skipping {log_source.name} due to configuration issues")
                    #     continue
                    
                    # Create connector with database configuration
                    if log_source.source_type in ['opensearch', 'elasticsearch']:
                        from src.ingestion.opensearch_connector import OpenSearchConnector
                        
                        connector = OpenSearchConnector(
                            host=log_source.host,
                            port=log_source.port,
                            username=log_source.username,
                            password=log_source.password,
                            use_ssl=log_source.use_ssl,
                            verify_certs=log_source.verify_certs
                        )
                        
                        # Get search duration from Service configuration (Task Management settings)
                        service = db.query(Service).filter(Service.id == log_source.service_id).first()
                        
                        # Determine search duration based on configured unit
                        # Priority: days > hours > minutes (only one should be set)
                        if service and service.log_fetch_duration_days:
                            search_duration_seconds = service.log_fetch_duration_days * 24 * 60 * 60
                            logger.info(f"[Task {task_id}] Using search duration: {service.log_fetch_duration_days} days")
                        elif service and service.log_fetch_duration_hours:
                            search_duration_seconds = service.log_fetch_duration_hours * 60 * 60
                            logger.info(f"[Task {task_id}] Using search duration: {service.log_fetch_duration_hours} hours")
                        elif service and service.log_fetch_duration_minutes:
                            search_duration_seconds = service.log_fetch_duration_minutes * 60
                            logger.info(f"[Task {task_id}] Using search duration: {service.log_fetch_duration_minutes} minutes")
                        else:
                            # Fallback to default 30 minutes if not configured
                            search_duration_seconds = 30 * 60
                            logger.warning(f"[Task {task_id}] No search duration configured, using default: 30 minutes")
                        
                        # Fetch logs with configured search duration
                        from datetime import datetime, timedelta
                        logs = connector.fetch_logs(
                            duration_seconds=search_duration_seconds,
                            log_levels=settings.log_levels_list,
                            max_logs=10000,
                            index_pattern=log_source.index_pattern
                        )
                        
                        logger.info(f"[Task {task_id}] Fetched {len(logs)} logs from {log_source.name}")
                        
                        if logs:
                            # Process logs with log source context
                            processor = LogProcessor()
                            stats = processor.process_logs(logs, log_source_id=log_source.id)
                            
                            # Update totals
                            total_logs += len(logs)
                            for key in total_stats:
                                total_stats[key] += stats.get(key, 0)
                            
                            source_results.append({
                                'log_source_id': log_source.id,
                                'log_source_name': log_source.name,
                                'logs_fetched': len(logs),
                                'stats': stats
                            })
                            
                            # Update last fetch time
                            log_source.last_fetch_at = datetime.utcnow()
                            log_source.connection_status = 'connected'
                            log_source.last_error = None
                        else:
                            logger.info(f"[Task {task_id}] No logs found for {log_source.name}")
                            source_results.append({
                                'log_source_id': log_source.id,
                                'log_source_name': log_source.name,
                                'logs_fetched': 0,
                                'stats': {}
                            })
                    
                    else:
                        logger.warning(f"[Task {task_id}] Unsupported log source type: {log_source.source_type}")
                        continue
                        
                except Exception as source_error:
                    logger.error(f"[Task {task_id}] Error fetching from {log_source.name}: {source_error}")
                    
                    # Update error status
                    log_source.connection_status = 'error'
                    log_source.last_error = str(source_error)
                    
                    source_results.append({
                        'log_source_id': log_source.id,
                        'log_source_name': log_source.name,
                        'logs_fetched': 0,
                        'error': str(source_error)
                    })
            
            # Commit database changes
            db.commit()
            
            logger.info(f"[Task {task_id}] Log fetch and process complete: {total_stats}")
            
            # Trigger on-demand code indexing if exceptions were detected
            if total_stats['exceptions_found'] > 0 and service_id:
                if _should_index_code_for_service(service_id):
                    logger.info(f"[Task {task_id}] Triggering on-demand code indexing for service {service_id}")
                    
                    # Mark as indexing in progress
                    _mark_indexing_in_progress(service_id)
                    
                    # Trigger indexing asynchronously with high priority
                    index_code_repository.apply_async(
                        kwargs={
                            'service_id': service_id,
                            'trigger_reason': 'exception_detected',
                            'force_full': False
                        },
                        priority=7  # High priority (0-9 scale, 9 is highest)
                    )
            
            return {
                'status': 'success',
                'task_id': task_id,
                'timestamp': datetime.utcnow().isoformat(),
                'total_logs_processed': total_logs,
                'total_stats': total_stats,
                'log_sources_processed': len(source_results),
                'source_results': source_results
            }
            
        finally:
            db.close()
        
    except Exception as e:
        logger.error(f"[Task {task_id}] Error: {e}", exc_info=True)
        return {
            'status': 'error',
            'task_id': task_id,
            'error': str(e)
        }





@celery_app.task(name='tasks.process_log_batch', bind=True)
def process_log_batch(self, logs: List[Dict[str, Any]], log_source_id: str) -> Dict[str, Any]:
    """
    Process a batch of logs asynchronously.
    
    This task can be called from the API to process logs in the background
    instead of blocking the API response.
    
    Args:
        logs: List of log entries to process
        log_source_id: Required log source ID for strict service association
        
    Returns:
        Processing statistics
    """
    task_id = self.request.id
    logger.info(f"[Task {task_id}] Processing batch of {len(logs)} logs")
    
    try:
        processor = LogProcessor()
        stats = processor.process_logs(logs, log_source_id)
        
        logger.info(f"[Task {task_id}] Batch processing complete: {stats}")
        
        return {
            'status': 'success',
            'task_id': task_id,
            'stats': stats
        }
        
    except Exception as e:
        logger.error(f"[Task {task_id}] Error: {e}", exc_info=True)
        return {
            'status': 'error',
            'task_id': task_id,
            'error': str(e)
        }


@celery_app.task(name='tasks.generate_rca_for_clusters', bind=True)
def generate_rca_for_clusters(self, service_id: str = None) -> Dict[str, Any]:
    """
    Generate RCA (Root Cause Analysis) for qualifying exception clusters.
    
    This task:
    1. Gets all active clusters (optionally filtered by service)
    2. Checks which ones need RCA
    3. Generates RCA using LLM
    4. Sends notifications
    
    Args:
        service_id: Optional service ID to generate RCA for specific service only
    
    Returns:
        RCA generation statistics
    """
    task_id = self.request.id
    logger.info(f"[Task {task_id}] Starting RCA generation")
    
    # Check if task is enabled
    if not task_config_manager.is_task_enabled('generate_rca_for_clusters'):
        logger.info(f"[Task {task_id}] Task is disabled, skipping execution")
        return {'status': 'skipped', 'reason': 'task_disabled'}
    
    if not settings.enable_llm_analysis:
        logger.info(f"[Task {task_id}] LLM analysis disabled, skipping")
        return {'status': 'skipped', 'reason': 'llm_disabled'}
    
    try:
        clusterer = ExceptionClusterer()
        analyzer = LLMAnalyzer()
        
        # Get active clusters (optionally filtered by service)
        if service_id:
            clusters = clusterer.list_active_clusters(limit=50, service_id=service_id)
            logger.info(f"[Task {task_id}] Found {len(clusters)} active clusters for service {service_id}")
        else:
            clusters = clusterer.list_active_clusters(limit=50)
            logger.info(f"[Task {task_id}] Found {len(clusters)} active clusters")
        
        rca_generated = 0
        rca_failed = 0
        
        for cluster in clusters:
            cluster_id = cluster.get('cluster_id')
            
            # Check if RCA should be generated
            if clusterer.should_trigger_rca(cluster_id):
                try:
                    logger.info(f"[Task {task_id}] Generating RCA for cluster {cluster_id}")
                    rca_id = analyzer.analyze_cluster(cluster_id)
                    
                    if rca_id:
                        rca_generated += 1
                        logger.info(f"[Task {task_id}] RCA generated: {rca_id}")
                    
                except Exception as e:
                    rca_failed += 1
                    logger.error(f"[Task {task_id}] RCA failed for {cluster_id}: {e}")
        
        result = {
            'status': 'success',
            'task_id': task_id,
            'clusters_checked': len(clusters),
            'rca_generated': rca_generated,
            'rca_failed': rca_failed
        }
        
        logger.info(f"[Task {task_id}] RCA generation complete: {result}")
        return result
        
    except Exception as e:
        logger.error(f"[Task {task_id}] Error: {e}", exc_info=True)
        return {
            'status': 'error',
            'task_id': task_id,
            'error': str(e)
        }


@celery_app.task(name='tasks.analyze_cluster', bind=True)
def analyze_cluster(self, cluster_id: str) -> Dict[str, Any]:
    """
    Generate RCA for a specific cluster (can be triggered manually or via API).
    
    Args:
        cluster_id: ID of the cluster to analyze
        
    Returns:
        RCA result
    """
    task_id = self.request.id
    logger.info(f"[Task {task_id}] Analyzing cluster {cluster_id}")
    
    try:
        analyzer = LLMAnalyzer()
        rca_id = analyzer.analyze_cluster(cluster_id)
        
        if rca_id:
            logger.info(f"[Task {task_id}] RCA generated: {rca_id}")
            return {
                'status': 'success',
                'task_id': task_id,
                'cluster_id': cluster_id,
                'rca_id': rca_id
            }
        else:
            return {
                'status': 'failed',
                'task_id': task_id,
                'cluster_id': cluster_id,
                'error': 'RCA generation returned None'
            }
            
    except Exception as e:
        logger.error(f"[Task {task_id}] Error: {e}", exc_info=True)
        return {
            'status': 'error',
            'task_id': task_id,
            'cluster_id': cluster_id,
            'error': str(e)
        }


@celery_app.task(name='tasks.index_code_repository', bind=True)
def index_code_repository(
    self,
    service_id: str = None,
    trigger_reason: str = 'manual',
    force_full: bool = False,
    repository_path: str = None,
    branch: str = 'main'
):
    """
    Index the code repository with on-demand and incremental indexing support.
    
    This task:
    1. Scans the configured Git repository (service-specific or global)
    2. Uses incremental indexing (only changed files since last run)
    3. Extracts code structure (functions, classes)
    4. Generates embeddings
    5. Stores in vector database and PostgreSQL
    6. Tracks Git commits and metadata
    7. Updates service indexing status
    
    Indexing Modes:
    - API Mode: Always fetches from remote (GitHub/GitLab API), supports true incremental indexing
    - Local Mode: Reads from local filesystem (user manages git pull manually)
    
    Args:
        service_id: Service ID to index (uses service-specific repo)
        trigger_reason: Why indexing was triggered (exception_detected, pre_rca, manual, webhook)
        force_full: Force full indexing instead of incremental
        repository_path: Override repository path (deprecated, use service_id)
        branch: Git branch to index (deprecated, use service config)
    
    Returns:
        Indexing statistics
    """
    task_id = self.request.id
    logger.info(f"[Task {task_id}] Starting code indexing for service {service_id}")
    logger.info(f"[Task {task_id}] Trigger reason: {trigger_reason}")
    logger.info(f"[Task {task_id}] Force full: {force_full}")
    
    # Check if task is enabled
    config = task_config_manager.get_task_config('index_code_repository')
    if not config['enabled']:
        logger.info(f"[Task {task_id}] Task 'index_code_repository' is disabled, skipping execution")
        return {
            'status': 'skipped',
            'reason': 'Task is disabled',
            'timestamp': datetime.utcnow().isoformat()
        }
    
    try:
        from src.storage.database import get_db
        from src.storage.models import Service
        logger.info("Reached here")
        # Get service configuration if service_id provided
        if service_id:
            with get_db() as db:

                service = db.query(Service).filter(Service.id == service_id).first()
                logger.info(f"Reached here1")

                if not service:
                    error_msg = f"Service {service_id} not found"
                    logger.error(f"[Task {task_id}] {error_msg}")
                    return {'status': 'error', 'error': error_msg}
                
                # Extract service configuration inside session
                use_api_mode = service.use_api_mode if hasattr(service, 'use_api_mode') else False
                repository_url = service.repository_url
                git_provider = service.git_provider if hasattr(service, 'git_provider') else None
                git_branch = service.git_branch or 'main'
                git_repo_path = service.git_repo_path
                access_token = service.access_token if hasattr(service, 'access_token') else None
                logger.info(f"Reached here2 ")

                # Validate configuration based on mode
                if use_api_mode:
                    # API mode: requires repository_url and access_token
                    if not repository_url:
                        error_msg = f"API mode requires repository_url for service {service_id}"
                        logger.error(f"[Task {task_id}] {error_msg}")
                        _mark_indexing_failed(service_id, error_msg)
                        return {'status': 'error', 'error': error_msg}
                    logger.info(f"[Task {task_id}] Using API mode: url={repository_url}, branch={git_branch}")
                else:
                    # Local mode: requires git_repo_path
                    if not git_repo_path:
                        error_msg = f"Local mode requires git_repo_path for service {service_id}"
                        logger.error(f"[Task {task_id}] {error_msg}")
                        _mark_indexing_failed(service_id, error_msg)
                        return {'status': 'error', 'error': error_msg}
                    logger.info(f"[Task {task_id}] Using Local mode: path={git_repo_path}, branch={git_branch}")
        
        # Initialize code indexer using factory
        from src.services.code_indexer_factory import CodeIndexerFactory
        logger.info(f"Reached here3 ")

        # Create indexer
        indexer = CodeIndexerFactory.create_from_service(
            service_data={
                'id': service_id,
                'use_api_mode': use_api_mode,
                'repository_url': repository_url,
                'git_provider': git_provider,
                'git_branch': git_branch,
                'git_repo_path': git_repo_path,
                'access_token': access_token,
            }
        )
        
        logger.info(f"[Task {task_id}] Using indexer: {indexer.__class__.__name__}")
        
        # Run indexing (incremental by default unless force_full=True)
        # API mode: Always fetches from remote (no auto_sync needed)
        # Local mode: TODO - implement auto_sync (git pull before indexing)
        if hasattr(indexer, 'index_repository'):
            stats = indexer.index_repository(
                languages=['python', 'java'],
                force_full=force_full
            )
        else:
            raise AttributeError(f"Indexer {indexer.__class__.__name__} does not have index_repository method")
        
        # Track Git metadata if git_service is available (LOCAL MODE ONLY)
        # API mode doesn't have local repository, so skip git_service
        if indexer.__class__.__name__ == 'CodeIndexer':
            # Local mode - has local repository
            try:
                from src.services.git_service import git_service
                git_stats = git_service.index_repository_with_git_metadata()
                stats['git_commits_tracked'] = git_stats.get('commits_tracked', 0)
                logger.info(f"[Task {task_id}] Git metadata tracked: {stats['git_commits_tracked']} commits")
            except Exception as git_error:
                logger.warning(f"[Task {task_id}] Git metadata indexing failed: {git_error}")
        else:
            # API mode - no local repository, skip git_service
            logger.info(f"[Task {task_id}] API mode: Skipping git_service (no local repository)")
            stats['git_commits_tracked'] = 0
        
        # Mark indexing as complete for service
        if service_id and hasattr(indexer, 'commit_sha') and indexer.commit_sha:
            _mark_indexing_complete(service_id, indexer.commit_sha)
        elif service_id:
            logger.warning(f"[Task {task_id}] No commit SHA available, skipping indexing metadata update")
        
        logger.info(f"[Task {task_id}] Code indexing complete: {stats}")
        
        return {
            'status': 'success',
            'task_id': task_id,
            'service_id': service_id,
            'trigger_reason': trigger_reason,
            'mode': stats.get('mode', 'unknown'),
            'files_indexed': stats.get('total_files', 0),
            'blocks_indexed': stats.get('total_blocks', 0),
            'errors': stats.get('errors', 0),
            'commit_sha': indexer.commit_sha,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        error_msg = f"Code indexing failed: {str(e)}"
        logger.error(f"[Task {task_id}] {error_msg}", exc_info=True)
        
        # Mark indexing as failed for service
        if service_id:
            _mark_indexing_failed(service_id, error_msg)
        
        return {
            'status': 'error',
            'task_id': task_id,
            'service_id': service_id,
            'error': error_msg,
            'timestamp': datetime.utcnow().isoformat()
        }


@celery_app.task(name='tasks.cleanup_old_data', bind=True)
def cleanup_old_data(self, days: int = 30) -> Dict[str, Any]:
    """
    Clean up old data from databases.
    
    Args:
        days: Delete data older than this many days
        
    Returns:
        Cleanup statistics
    """
    task_id = self.request.id
    logger.info(f"[Task {task_id}] Starting cleanup (older than {days} days)")
    
    # Check if task is enabled
    if not task_config_manager.is_task_enabled('cleanup_old_data'):
        logger.info(f"[Task {task_id}] Task is disabled, skipping execution")
        return {'status': 'skipped', 'reason': 'task_disabled'}
    
    try:
        from src.storage.database import get_db
        from datetime import timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # This is a placeholder - implement actual cleanup logic
        # based on your database schema
        
        logger.info(f"[Task {task_id}] Cleanup complete")
        
        return {
            'status': 'success',
            'task_id': task_id,
            'cutoff_date': cutoff_date.isoformat(),
            'message': 'Cleanup completed (implement actual logic)'
        }
        
    except Exception as e:
        logger.error(f"[Task {task_id}] Error: {e}", exc_info=True)
        return {
            'status': 'error',
            'task_id': task_id,
            'error': str(e)
        }


# ============================================================================
# TASK MONITORING
# ============================================================================

@celery_app.task(name='tasks.health_check')
def health_check() -> Dict[str, Any]:
    """
    Health check task to verify Celery workers are running.
    
    Returns:
        Health status
    """
    return {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'message': 'Celery worker is running'
    }


# Export celery app for CLI
__all__ = ['celery_app']
