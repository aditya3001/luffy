"""
Exception clustering inspired by LogAI patterns.
Groups similar exceptions using fingerprinting and semantic similarity.
"""
import uuid
from typing import List, Dict, Any, Optional
from collections import defaultdict
from datetime import datetime, timedelta
import logging
from src.config import settings
from src.storage.vector_db import vector_db
from src.storage.database import get_db
from src.storage.models import ExceptionCluster, Service, LogSource

logger = logging.getLogger(__name__)


class ExceptionClusterer:
    """Cluster exceptions using fingerprinting and embeddings"""
    
    def __init__(self, threshold: float = None):
        self.threshold = threshold or settings.clustering_threshold
        self.static_clusters = defaultdict(list)  # fingerprint -> list of log IDs
    
    def _parse_time_filter(self, time_filter: Optional[str]) -> Optional[datetime]:
        """
        Parse time filter string to datetime cutoff.
        
        Supports:
        - Preset filters: '5m', '10m', '30m', '1h', '6h', '24h', '7d', '30d'
        - Custom range: 'custom:start_iso:end_iso' (returns start datetime)
        
        Returns the cutoff datetime (exceptions with last_seen >= cutoff will be included)
        """
        if not time_filter:
            return None
            
        # Handle custom date range format: custom:start_iso:end_iso
        if time_filter.startswith('custom:'):
            try:
                parts = time_filter.split(':', 2)
                if len(parts) == 3:
                    start_iso = parts[1]
                    # Parse ISO format datetime
                    from dateutil import parser
                    start_dt = parser.isoparse(start_iso)
                    return start_dt
            except Exception as e:
                logger.warning(f"Failed to parse custom time filter '{time_filter}': {e}")
                return None
        
        # Handle preset time filters
        now = datetime.utcnow()
        
        if time_filter == '5m':
            return now - timedelta(minutes=5)
        elif time_filter == '10m':
            return now - timedelta(minutes=10)
        elif time_filter == '30m':
            return now - timedelta(minutes=30)
        elif time_filter == '1h':
            return now - timedelta(hours=1)
        elif time_filter == '6h':
            return now - timedelta(hours=6)
        elif time_filter == '24h':
            return now - timedelta(hours=24)
        elif time_filter == '7d':
            return now - timedelta(days=7)
        elif time_filter == '30d':
            return now - timedelta(days=30)
        else:
            return None
    
    def cluster_exceptions(
        self,
        exceptions: List[Dict[str, Any]],
        log_source_id: str
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Cluster exceptions using multi-level fingerprinting.
        
        For logs WITH stack traces: Uses traditional fingerprinting (exception type + stack frames)
        For logs WITHOUT stack traces: Uses multi-level fingerprinting (template, semantic, category)
        
        Args:
            exceptions: List of extracted exceptions
            log_source_id: Required log source ID for strict service association
        
        Returns:
            Dictionary mapping cluster_id to list of exceptions
        """
        clusters = {}
        
        # Separate exceptions with and without stack traces
        with_stack = [exc for exc in exceptions if exc.get('has_stack_trace', False)]
        without_stack = [exc for exc in exceptions if not exc.get('has_stack_trace', False)]
        
        logger.info(f"Processing {len(with_stack)} exceptions with stack trace, "
                   f"{len(without_stack)} without stack trace")
        
        # Step 1: Cluster exceptions WITH stack traces (traditional method)
        fingerprint_groups = defaultdict(list)
        for exc in with_stack:
            fp = exc.get('fingerprint_static')
            if fp:
                fingerprint_groups[fp].append(exc)
        
        for fingerprint, group_exceptions in fingerprint_groups.items():
            cluster_id = self._get_or_create_cluster(
                fingerprint, 
                group_exceptions, 
                log_source_id,
                clustering_strategy='stack_trace'
            )
            clusters[cluster_id] = group_exceptions
        
        # Step 2: Cluster exceptions WITHOUT stack traces (multi-level fingerprinting)
        # Try template matching first (most specific)
        template_groups = defaultdict(list)
        for exc in without_stack:
            fp_template = exc.get('fingerprint_template')
            if fp_template:
                template_groups[fp_template].append(exc)
        
        for fingerprint, group_exceptions in template_groups.items():
            cluster_id = self._get_or_create_cluster(
                fingerprint,
                group_exceptions,
                log_source_id,
                clustering_strategy='template',
                additional_metadata={
                    'fingerprint_semantic': group_exceptions[0].get('fingerprint_semantic'),
                    'fingerprint_category': group_exceptions[0].get('fingerprint_category'),
                    'error_category': group_exceptions[0].get('error_category'),
                    'key_terms': group_exceptions[0].get('key_terms', []),
                }
            )
            clusters[cluster_id] = group_exceptions
        
        logger.info(f"Clustered {len(exceptions)} exceptions into {len(clusters)} clusters "
                   f"({len(fingerprint_groups)} with stack, {len(template_groups)} without stack)")
        return clusters
    
    def _get_or_create_cluster(
        self,
        fingerprint: str,
        exceptions: List[Dict[str, Any]],
        log_source_id: str,
        clustering_strategy: str = 'stack_trace',
        additional_metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Get existing cluster or create new one with strict service/log_source association.
        
        Args:
            fingerprint: Primary fingerprint for clustering
            exceptions: List of exceptions in this cluster
            log_source_id: Required log source ID
            clustering_strategy: Strategy used ('stack_trace' or 'template')
            additional_metadata: Additional metadata for template-based clusters
        """
        
        if not log_source_id:
            raise ValueError("log_source_id is required for strict service association")
        
        with get_db() as db:
            # Get service_id from log_source_id (required)
            log_source = db.query(LogSource).filter_by(id=log_source_id).first()
            if not log_source:
                raise ValueError(f"Log source {log_source_id} not found in database")
            
            service_id = log_source.service_id
            
            # Check if cluster with this fingerprint exists for this service and log source
            query = db.query(ExceptionCluster).filter_by(
                fingerprint_static=fingerprint,
                service_id=service_id
            )
            
            # Add log_source_id filter (including None case)
            query = query.filter(
                ExceptionCluster.log_source_id == log_source_id
            )
            
            existing_cluster = query.first()
            
            if existing_cluster:
                # Update cluster metadata
                existing_cluster.cluster_size += len(exceptions)
                existing_cluster.last_seen = datetime.utcnow()
                existing_cluster.frequency_24h += len(exceptions)
                db.commit()
                logger.debug(f"Updated existing cluster: {existing_cluster.cluster_id}")
                return existing_cluster.cluster_id
            
            # Create new cluster
            representative = exceptions[0]  # Use first as representative
            
            cluster_id = f"cluster_{uuid.uuid4().hex[:12]}"
            
            service = db.query(Service).filter_by(id=service_id).first()
            if not service:
                service = Service(
                    id=service_id,
                    name=service_id,
                    version='unknown',
                    commit_sha=''
                )
                db.add(service)
            
            cluster = ExceptionCluster(
                cluster_id=cluster_id,
                service_id=service_id,
                log_source_id=log_source_id,
                exception_type=representative.get('exception_type', 'UnknownError'),
                exception_message=representative.get('exception_message', ''),
                fingerprint_static=fingerprint,
                representative_log_id=representative.get('log_id'),
                stack_trace=representative.get('stack_frames', []),
                logger_path=representative.get('logger', 'unknown'),  # Store logger path
                cluster_size=len(exceptions),
                first_seen=datetime.utcnow(),
                last_seen=datetime.utcnow(),
                frequency_24h=len(exceptions)
            )
            
            db.add(cluster)
            db.commit()
            
            logger.info(f"Created new cluster: {cluster_id} with {len(exceptions)} exceptions")
            return cluster_id
    
    def should_trigger_rca(self, cluster_id: str) -> bool:
        """
        Determine if a cluster should trigger RCA analysis.
        
        Criteria:
        - High frequency (> 10 in 24h)
        - New cluster (first time seen)
        - User request
        """
        with get_db() as db:
            cluster = db.query(ExceptionCluster).filter_by(cluster_id=cluster_id).first()
            
            if not cluster:
                return False
            
            # Already has RCA
            if cluster.has_rca:
                return False
            
            # High frequency
            if cluster.frequency_24h >= 10:
                logger.info(f"Cluster {cluster_id} triggered RCA: high frequency ({cluster.frequency_24h})")
                return True
            
            # New cluster (first seen recently)
            if (datetime.utcnow() - cluster.first_seen).total_seconds() < 3600:
                logger.info(f"Cluster {cluster_id} triggered RCA: new cluster")
                return True
            
            return False
    
    def get_cluster_details(self, cluster_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a cluster"""
        with get_db() as db:
            cluster = db.query(ExceptionCluster).filter_by(cluster_id=cluster_id).first()
            
            if not cluster:
                return None
            
            # Determine severity based on cluster size and frequency
            severity = 'low'
            if cluster.cluster_size > 100 or cluster.frequency_24h > 50:
                severity = 'critical'
            elif cluster.cluster_size > 50 or cluster.frequency_24h > 20:
                severity = 'high'
            elif cluster.cluster_size > 10 or cluster.frequency_24h > 5:
                severity = 'medium'
            
            # Get service name
            service_name = cluster.service_id
            if cluster.service_id:
                service = db.query(Service).filter_by(id=cluster.service_id).first()
                if service:
                    service_name = service.name
            
            return {
                'cluster_id': cluster.cluster_id,
                'exception_type': cluster.exception_type,
                'signature': cluster.fingerprint_static or '',
                'count': cluster.cluster_size,
                'first_seen': cluster.first_seen.isoformat(),
                'last_seen': cluster.last_seen.isoformat(),
                'severity': severity,
                'services': [service_name] if service_name else [],
                'has_rca': cluster.has_rca,
                'status': cluster.status or 'active',
                'status_updated_at': cluster.status_updated_at.isoformat() if cluster.status_updated_at else None,
                'status_updated_by': cluster.status_updated_by,
                'logger_path': cluster.logger_path or 'unknown',  # Logger path from log entry
                # Additional fields for detail view
                'exception_message': cluster.exception_message,
                'stack_trace': cluster.stack_trace,
                'frequency_24h': cluster.frequency_24h,
            }
    
    def list_active_clusters(
        self, 
        status: str = 'active',
        service_id: Optional[str] = None,
        log_source_id: Optional[str] = None,
        time_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List all clusters filtered by status, service, log source, and time.
        Returns all matching clusters without limit.
        
        Args:
            status: Filter by status ('active', 'skipped', 'resolved', or None for all)
            service_id: Optional service filter
            log_source_id: Optional log source filter
            time_filter: Optional time filter (5m, 10m, 30m, 1h, 6h, 24h, 7d, 30d)
                         If not provided, shows all exceptions regardless of time
        
        Returns:
            List of all matching clusters ordered by last_seen (most recent first)
        """
        with get_db() as db:
            query = db.query(ExceptionCluster).order_by(
                ExceptionCluster.last_seen.desc()
            )
            
            # Add time filter if provided
            if time_filter:
                # Handle custom date range with both start and end
                if time_filter.startswith('custom:'):
                    try:
                        parts = time_filter.split(':', 2)
                        if len(parts) == 3:
                            from dateutil import parser
                            start_iso, end_iso = parts[1], parts[2]
                            start_dt = parser.isoparse(start_iso)
                            end_dt = parser.isoparse(end_iso)
                            query = query.filter(
                                ExceptionCluster.last_seen >= start_dt,
                                ExceptionCluster.last_seen <= end_dt
                            )
                    except Exception as e:
                        logger.warning(f"Failed to parse custom time filter '{time_filter}': {e}")
                else:
                    # Handle preset time filters
                    time_cutoff = self._parse_time_filter(time_filter)
                    if time_cutoff:
                        query = query.filter(ExceptionCluster.last_seen >= time_cutoff)
            
            # Filter by status if provided
            if status:
                query = query.filter(ExceptionCluster.status == status)
            
            # Filter by service if provided
            if service_id:
                query = query.filter(ExceptionCluster.service_id == service_id)
            
            # Filter by log source if provided
            if log_source_id:
                query = query.filter(ExceptionCluster.log_source_id == log_source_id)
            
            # Get all matching clusters (no limit)
            clusters = query.all()
            
            logger.info(f"Retrieved {len(clusters)} clusters (status={status}, service={service_id}, time_filter={time_filter})")
            return [self.get_cluster_details(c.cluster_id) for c in clusters]
    
    def update_cluster_status(
        self, 
        cluster_id: str, 
        status: str, 
        updated_by: str = 'system'
    ) -> bool:
        """
        Update the status of a cluster.
        
        Args:
            cluster_id: ID of the cluster
            status: New status ('active', 'skipped', 'resolved')
            updated_by: User ID or system identifier
            
        Returns:
            True if successful, False otherwise
        """
        if status not in ['active', 'skipped', 'resolved']:
            logger.error(f"Invalid status: {status}")
            return False
        
        with get_db() as db:
            cluster = db.query(ExceptionCluster).filter_by(cluster_id=cluster_id).first()
            
            if not cluster:
                logger.error(f"Cluster not found: {cluster_id}")
                return False
            
            cluster.status = status
            cluster.status_updated_at = datetime.utcnow()
            cluster.status_updated_by = updated_by
            cluster.updated_at = datetime.utcnow()
            
            db.commit()
            logger.info(f"Updated cluster {cluster_id} status to '{status}' by {updated_by}")
            return True
    
    def skip_cluster(self, cluster_id: str, updated_by: str = 'user') -> bool:
        """Mark a cluster as skipped"""
        return self.update_cluster_status(cluster_id, 'skipped', updated_by)
    
    def resolve_cluster(self, cluster_id: str, updated_by: str = 'user') -> bool:
        """Mark a cluster as resolved"""
        return self.update_cluster_status(cluster_id, 'resolved', updated_by)
    
    def reactivate_cluster(self, cluster_id: str, updated_by: str = 'user') -> bool:
        """Reactivate a skipped or resolved cluster"""
        return self.update_cluster_status(cluster_id, 'active', updated_by)
    

