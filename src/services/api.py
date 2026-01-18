"""
FastAPI REST API for the observability platform.
Provides endpoints for querying clusters, RCA results, and triggering analysis.
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
from src.config import settings
from src.services.processor import LogProcessor
from src.services.clustering import ExceptionClusterer
from src.services.llm_analyzer import LLMAnalyzer
from src.services.task_config import task_config_manager
from src.services.stats_service import stats_service
from src.storage.database import init_db
from src.storage.vector_db import vector_db
from src.services.api_git import router as git_router
from src.services.api_services import router as services_router
from src.services.api_task_management import router as task_management_router
from src.services.api_log_sources import router as log_sources_router
from src.services.api_service_config import router as service_config_router
from src.services.api_code_indexing import router as code_indexing_router
from src.services.api_ingest import router as ingest_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="AI-Powered Log Observability API",
    description="API for exception analysis and root cause detection",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
processor = LogProcessor()
clusterer = ExceptionClusterer()
analyzer = LLMAnalyzer()


# Request/Response Models
class ProcessLogFileRequest(BaseModel):
    file_path: str
    log_source_id: str


class GenerateRCARequest(BaseModel):
    cluster_id: str


class FeedbackRequest(BaseModel):
    cluster_id: str
    rca_id: str
    is_helpful: bool
    accuracy_rating: Optional[int] = None
    comments: Optional[str] = None


class UpdateTaskConfigRequest(BaseModel):
    enabled: Optional[bool] = None
    interval_minutes: Optional[int] = None
    cron: Optional[str] = None
    modified_by: Optional[str] = "api"


# Include routers
app.include_router(git_router)
app.include_router(services_router)
app.include_router(task_management_router)
app.include_router(log_sources_router)
app.include_router(service_config_router)
app.include_router(code_indexing_router)
app.include_router(ingest_router)  # Fluent Bit log ingestion

# API Endpoints
@app.on_event("startup")
async def startup_event():
    """Initialize database and services on startup"""
    logger.info("Starting API server...")
    try:
        init_db()
        vector_db.init_collections()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "AI-Powered Log Observability API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.post("/api/v1/process")
async def process_log_file(
    request: ProcessLogFileRequest,
    background_tasks: BackgroundTasks
):
    """
    Process a log file.
    This runs synchronously for now but can be made async with background tasks.
    """
    try:
        stats = processor.process_log_file(request.file_path, request.log_source_id)
        return {
            "status": "success",
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Error processing log file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/clusters")
async def list_clusters(
    status: Optional[str] = 'active',
    service_id: Optional[str] = None,
    log_source_id: Optional[str] = None,
    time_filter: Optional[str] = None
):
    """
    List exception clusters filtered by status, service, log source, and time.
    
    Args:
        status: Filter by status ('active', 'skipped', 'resolved', 'all')
        service_id: Optional service filter
        log_source_id: Optional log source filter
        time_filter: Optional time filter (5m, 10m, 30m, 1h, 6h, 24h, 7d, 30d)
                     If not provided, shows all exceptions regardless of time
    
    Returns all matching clusters without limit.
    """
    try:
        # If status is 'all', pass None to get all clusters
        filter_status = None if status == 'all' else status
        clusters = clusterer.list_active_clusters(
            status=filter_status,
            service_id=service_id,
            log_source_id=log_source_id,
            time_filter=time_filter
        )
        return {
            "status": "success",
            "count": len(clusters),
            "clusters": clusters
        }
    except Exception as e:
        logger.error(f"Error listing clusters: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/clusters/{cluster_id}")
async def get_cluster(cluster_id: str):
    """Get details of a specific cluster"""
    try:
        cluster = clusterer.get_cluster_details(cluster_id)
        if not cluster:
            raise HTTPException(status_code=404, detail="Cluster not found")
        return {
            "status": "success",
            "cluster": cluster
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting cluster: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/clusters/{cluster_id}/skip")
async def skip_cluster(cluster_id: str, updated_by: Optional[str] = 'user'):
    """Mark a cluster as skipped"""
    try:
        success = clusterer.skip_cluster(cluster_id, updated_by)
        if not success:
            raise HTTPException(status_code=404, detail="Cluster not found or update failed")
        return {
            "status": "success",
            "message": f"Cluster {cluster_id} marked as skipped",
            "cluster_id": cluster_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error skipping cluster: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/clusters/{cluster_id}/resolve")
async def resolve_cluster(cluster_id: str, updated_by: Optional[str] = 'user'):
    """Mark a cluster as resolved"""
    try:
        success = clusterer.resolve_cluster(cluster_id, updated_by)
        if not success:
            raise HTTPException(status_code=404, detail="Cluster not found or update failed")
        return {
            "status": "success",
            "message": f"Cluster {cluster_id} marked as resolved",
            "cluster_id": cluster_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving cluster: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/clusters/{cluster_id}/reactivate")
async def reactivate_cluster(cluster_id: str, updated_by: Optional[str] = 'user'):
    """Reactivate a skipped or resolved cluster"""
    try:
        success = clusterer.reactivate_cluster(cluster_id, updated_by)
        if not success:
            raise HTTPException(status_code=404, detail="Cluster not found or update failed")
        return {
            "status": "success",
            "message": f"Cluster {cluster_id} reactivated",
            "cluster_id": cluster_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reactivating cluster: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/rca/{cluster_id}")
async def get_rca(cluster_id: str):
    """Get RCA result for a cluster"""
    try:
        rca = analyzer.get_rca_result(cluster_id)
        if not rca:
            raise HTTPException(status_code=404, detail="RCA not found")
        return {
            "status": "success",
            "rca": rca
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting RCA: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/rca/generate")
async def generate_rca(request: GenerateRCARequest):
    """Trigger RCA generation for a cluster"""
    try:
        rca_id = analyzer.analyze_cluster(request.cluster_id)
        if not rca_id:
            raise HTTPException(status_code=500, detail="Failed to generate RCA")
        return {
            "status": "success",
            "rca_id": rca_id,
            "message": "RCA generated successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating RCA: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/feedback")
async def submit_feedback(request: FeedbackRequest):
    """Submit feedback on RCA result"""
    try:
        # TODO: Implement feedback storage
        return {
            "status": "success",
            "message": "Feedback submitted successfully"
        }
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/stats")
async def get_stats(service_id: Optional[str] = None, time_filter: Optional[str] = None):
    """Get dashboard statistics, optionally filtered by service and time"""
    try:
        stats = stats_service.get_dashboard_stats(service_id=service_id, time_filter=time_filter)
        return {
            "status": "success",
            **stats
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/trends")
def get_exception_trends(days: int = 7, service_id: Optional[str] = None, log_source_id: Optional[str] = None):
    """
    Get exception trends over time (active exceptions only).
    
    Args:
        days: Number of days to include (1-30, default 7)
        service_id: Optional service filter
        log_source_id: Optional log source filter
    """
    if days < 1 or days > 30:
        raise HTTPException(status_code=400, detail="Days must be between 1 and 30")
    
    try:
        trends = stats_service.get_exception_trends(days, service_id, log_source_id)
        return {
            "trends": trends,
            "period_days": days,
            "service_id": service_id,
            "log_source_id": log_source_id,
            "total_data_points": len(trends)
        }
    except Exception as e:
        logger.error(f"Error getting exception trends: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get exception trends")


@app.get("/api/v1/stats/services")
async def get_exceptions_by_service(limit: int = 10):
    """
    Get exception counts grouped by service.
    
    Args:
        limit: Maximum number of services to return (default 10)
    """
    try:
        services = stats_service.get_exceptions_by_service(limit=limit)
        return {
            "status": "success",
            "services": services
        }
    except Exception as e:
        logger.error(f"Error getting service stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/stats/severity")
async def get_severity_distribution():
    """Get distribution of exceptions by severity"""
    try:
        distribution = stats_service.get_severity_distribution()
        return {
            "status": "success",
            "distribution": distribution
        }
    except Exception as e:
        logger.error(f"Error getting severity distribution: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# TASK CONFIGURATION ENDPOINTS
# ============================================================================

@app.get("/api/v1/tasks")
async def list_tasks():
    """
    List all periodic tasks and their configurations.
    
    Returns:
        - task_name: Name of the task
        - enabled: Whether the task is currently enabled
        - interval_minutes: Interval in minutes (for interval-based tasks)
        - cron: Cron expression (for cron-based tasks)
        - description: Task description
        - last_modified: Last modification timestamp
        - modified_by: Who/what modified the config
    """
    try:
        configs = task_config_manager.get_all_task_configs()
        return {
            "status": "success",
            "tasks": configs
        }
    except Exception as e:
        logger.error(f"Error listing tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/tasks/{task_name}")
async def get_task_config(task_name: str):
    """
    Get configuration for a specific task.
    
    Args:
        task_name: Name of the task (e.g., 'fetch_and_process_logs')
    """
    try:
        config = task_config_manager.get_task_config(task_name)
        if not config:
            raise HTTPException(status_code=404, detail=f"Task '{task_name}' not found")
        
        return {
            "status": "success",
            "task": config
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/v1/tasks/{task_name}")
async def update_task_config(task_name: str, request: UpdateTaskConfigRequest):
    """
    Update configuration for a specific task.
    
    Args:
        task_name: Name of the task
        request: Configuration updates
    
    Body:
        - enabled: Enable/disable the task (optional)
        - interval_minutes: Change interval (optional, for interval-based tasks)
        - cron: Change cron expression (optional, for cron-based tasks)
        - modified_by: Who is making the change (optional, defaults to 'api')
    
    Note: Changes take effect on the next scheduled run.
    To apply immediately, restart Celery Beat.
    """
    try:
        success = task_config_manager.update_task_config(
            task_name=task_name,
            enabled=request.enabled,
            interval_minutes=request.interval_minutes,
            cron=request.cron,
            modified_by=request.modified_by
        )
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to update task '{task_name}'. Task may not exist."
            )
        
        updated_config = task_config_manager.get_task_config(task_name)
        return {
            "status": "success",
            "message": f"Task '{task_name}' updated successfully",
            "task": updated_config
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating task config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/tasks/{task_name}/enable")
async def enable_task(task_name: str):
    """
    Enable a periodic task.
    
    Args:
        task_name: Name of the task to enable
    """
    try:
        success = task_config_manager.enable_task(task_name)
        if not success:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to enable task '{task_name}'. Task may not exist."
            )
        
        return {
            "status": "success",
            "message": f"Task '{task_name}' enabled successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enabling task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/tasks/{task_name}/disable")
async def disable_task(task_name: str):
    """
    Disable a periodic task.
    
    Args:
        task_name: Name of the task to disable
    """
    try:
        success = task_config_manager.disable_task(task_name)
        if not success:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to disable task '{task_name}'. Task may not exist."
            )
        
        return {
            "status": "success",
            "message": f"Task '{task_name}' disabled successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disabling task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/tasks/{task_name}/reset")
async def reset_task_config(task_name: str):
    """
    Reset a task to its default configuration.
    
    Args:
        task_name: Name of the task to reset
    """
    try:
        success = task_config_manager.reset_task_config(task_name)
        if not success:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to reset task '{task_name}'. Task may not exist."
            )
        
        updated_config = task_config_manager.get_task_config(task_name)
        return {
            "status": "success",
            "message": f"Task '{task_name}' reset to default configuration",
            "task": updated_config
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting task config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Run server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.log_level.lower()
    )
