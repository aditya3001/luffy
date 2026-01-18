"""
Enhanced task management API endpoints for multi-service architecture.
Provides endpoints for managing per-service and per-log-source tasks.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
from sqlalchemy.orm import Session
from src.storage.database import get_db_dependency
from src.storage.models import Service, LogSource
from src.services.task_config_enhanced import enhanced_task_config_manager, LogSourceTaskConfig, ServiceTaskConfig

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/task-management", tags=["task-management"])

# Request/Response Models
class LogSourceTaskRequest(BaseModel):
    fetch_enabled: Optional[bool] = None
    fetch_interval_minutes: Optional[int] = Field(None, ge=1, le=1440)

class LogSourceTaskResponse(BaseModel):
    log_source_id: str
    service_id: str
    service_name: str
    log_source_name: str
    fetch_enabled: bool
    fetch_interval_minutes: int
    last_fetch_at: Optional[str]
    last_error: Optional[str]
    modified_at: str
    modified_by: str

class ServiceTaskRequest(BaseModel):
    # Log fetch duration - how far back to search in OpenSearch
    log_fetch_duration_minutes: Optional[int] = Field(None, ge=1, le=43200)  # Up to 30 days in minutes
    log_fetch_duration_hours: Optional[int] = Field(None, ge=1, le=720)  # Up to 30 days in hours
    log_fetch_duration_days: Optional[int] = Field(None, ge=1, le=30)  # Up to 30 days
    
    rca_generation_enabled: Optional[bool] = None
    rca_generation_interval_minutes: Optional[int] = Field(None, ge=1, le=1440)
    code_indexing_enabled: Optional[bool] = None

class ServiceTaskResponse(BaseModel):
    service_id: str
    service_name: str
    
    # Log Fetch Configuration - Duration for OpenSearch query
    log_fetch_duration_minutes: Optional[int]
    log_fetch_duration_hours: Optional[int]
    log_fetch_duration_days: Optional[int]
    last_log_fetch: Optional[datetime]
    next_log_fetch: Optional[datetime]  # Calculated from Celery Beat schedule
    
    # RCA Configuration
    rca_generation_enabled: bool
    rca_generation_interval_minutes: int
    last_rca_generation: Optional[datetime]
    next_rca_generation: Optional[datetime]  # Calculated from Celery Beat schedule
    
    # Code Indexing Configuration
    code_indexing_enabled: bool
    code_indexing_status: Optional[str]
    last_code_indexing: Optional[datetime]
    next_code_indexing: Optional[datetime]
    
    # Counts
    log_sources_count: int
    active_log_sources_count: int
    
    # Metadata
    modified_at: str
    modified_by: str

class TaskOverviewResponse(BaseModel):
    services: List[ServiceTaskResponse]
    total_log_sources: int
    active_log_sources: int
    total_services: int
    active_services: int

# ============================================================================
# SERVICE TASK MANAGEMENT
# ============================================================================

@router.get("/services", response_model=List[ServiceTaskResponse])
def list_service_tasks(db: Session = Depends(get_db_dependency)):
    """List task configurations for all services"""
    try:
        services = db.query(Service).filter(Service.is_active == True).all()
        
        result = []
        for service in services:
            # Get task configuration
            config = enhanced_task_config_manager.get_service_config(service.id)
            
            # Count log sources
            total_log_sources = db.query(LogSource).filter(
                LogSource.service_id == service.id,
                LogSource.is_active == True
            ).count()
            
            active_log_sources = db.query(LogSource).filter(
                LogSource.service_id == service.id,
                LogSource.is_active == True,
                LogSource.fetch_enabled == True
            ).count()
            
            result.append(ServiceTaskResponse(
                service_id=service.id,
                service_name=service.name,
                rca_enabled=config.rca_enabled,
                rca_interval_minutes=config.rca_interval_minutes,
                index_code_enabled=config.index_code_enabled,
                index_code_cron=config.index_code_cron,
                cleanup_enabled=config.cleanup_enabled,
                cleanup_cron=config.cleanup_cron,
                log_sources_count=total_log_sources,
                active_log_sources_count=active_log_sources,
                modified_at=config.modified_at,
                modified_by=config.modified_by
            ))
        
        return result
        
    except Exception as e:
        logger.error(f"Error listing service tasks: {e}")
        raise HTTPException(status_code=500, detail="Failed to list service tasks")

@router.get("/services/{service_id}", response_model=ServiceTaskResponse)
def get_service_tasks(service_id: str, db: Session = Depends(get_db_dependency)):
    """Get task configuration for a specific service with real-time status"""
    try:
        from src.services.task_execution_tracker import calculate_next_run
        
        service = db.query(Service).filter(Service.id == service_id).first()
        if not service:
            raise HTTPException(status_code=404, detail="Service not found")
        
        # Count log sources
        total_log_sources = db.query(LogSource).filter(
            LogSource.service_id == service_id,
            LogSource.is_active == True
        ).count()
        
        active_log_sources = db.query(LogSource).filter(
            LogSource.service_id == service_id,
            LogSource.is_active == True,
            LogSource.fetch_enabled == True
        ).count()
        
        # Next run times are managed by Celery Beat scheduler
        # We just return None or estimate based on last run + typical interval
        next_log_fetch = None  # Managed by Celery Beat
        next_rca = None  # Managed by Celery Beat
        next_code_indexing = None  # Managed by Celery Beat
        
        return ServiceTaskResponse(
            service_id=service.id,
            service_name=service.name,
            log_fetch_duration_minutes=service.log_fetch_duration_minutes,
            log_fetch_duration_hours=service.log_fetch_duration_hours,
            log_fetch_duration_days=service.log_fetch_duration_days,
            last_log_fetch=service.last_log_fetch,
            next_log_fetch=next_log_fetch,
            rca_generation_enabled=service.rca_generation_enabled or False,
            rca_generation_interval_minutes=service.rca_generation_interval_minutes or 15,
            last_rca_generation=service.last_rca_generation,
            next_rca_generation=next_rca,
            code_indexing_enabled=service.code_indexing_enabled or False,
            code_indexing_status=service.code_indexing_status,
            last_code_indexing=service.last_code_indexing,
            next_code_indexing=next_code_indexing,
            log_sources_count=total_log_sources,
            active_log_sources_count=active_log_sources,
            modified_at=service.updated_at.isoformat() if service.updated_at else datetime.utcnow().isoformat(),
            modified_by="system"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting service tasks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get service tasks")

@router.put("/services/{service_id}", response_model=ServiceTaskResponse)
def update_service_tasks(service_id: str, request: ServiceTaskRequest, db: Session = Depends(get_db_dependency)):
    """Update task configuration for a service"""
    try:
        from src.services.task_execution_tracker import calculate_next_run
        
        service = db.query(Service).filter(Service.id == service_id).first()
        if not service:
            raise HTTPException(status_code=404, detail="Service not found")
        
        # Update fields if provided - save directly to Service model
        if request.log_fetch_duration_minutes is not None:
            service.log_fetch_duration_minutes = request.log_fetch_duration_minutes
        if request.log_fetch_duration_hours is not None:
            service.log_fetch_duration_hours = request.log_fetch_duration_hours
        if request.log_fetch_duration_days is not None:
            service.log_fetch_duration_days = request.log_fetch_duration_days
        if request.rca_generation_enabled is not None:
            service.rca_generation_enabled = request.rca_generation_enabled
        if request.rca_generation_interval_minutes is not None:
            service.rca_generation_interval_minutes = request.rca_generation_interval_minutes
        if request.code_indexing_enabled is not None:
            service.code_indexing_enabled = request.code_indexing_enabled
        
        service.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(service)
        
        logger.info(f"Updated task configuration for service {service_id}")
        
        # Count log sources
        total_log_sources = db.query(LogSource).filter(
            LogSource.service_id == service_id,
            LogSource.is_active == True
        ).count()
        
        active_log_sources = db.query(LogSource).filter(
            LogSource.service_id == service_id,
            LogSource.is_active == True,
            LogSource.fetch_enabled == True
        ).count()
        
        # Next run times managed by Celery Beat
        next_log_fetch = None
        next_rca = None
        next_code_indexing = None
        
        return ServiceTaskResponse(
            service_id=service.id,
            service_name=service.name,
            log_fetch_duration_minutes=service.log_fetch_duration_minutes,
            log_fetch_duration_hours=service.log_fetch_duration_hours,
            log_fetch_duration_days=service.log_fetch_duration_days,
            last_log_fetch=service.last_log_fetch,
            next_log_fetch=next_log_fetch,
            rca_generation_enabled=service.rca_generation_enabled or False,
            rca_generation_interval_minutes=service.rca_generation_interval_minutes or 15,
            last_rca_generation=service.last_rca_generation,
            next_rca_generation=next_rca,
            code_indexing_enabled=service.code_indexing_enabled or False,
            code_indexing_status=service.code_indexing_status,
            last_code_indexing=service.last_code_indexing,
            next_code_indexing=next_code_indexing,
            log_sources_count=total_log_sources,
            active_log_sources_count=active_log_sources,
            modified_at=service.updated_at.isoformat(),
            modified_by="api"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating service tasks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update service tasks")

# ============================================================================
# LOG SOURCE TASK MANAGEMENT
# ============================================================================

@router.get("/services/{service_id}/log-sources", response_model=List[LogSourceTaskResponse])
def list_log_source_tasks(service_id: str, db: Session = Depends(get_db_dependency)):
    """List task configurations for log sources in a service"""
    try:
        service = db.query(Service).filter(Service.id == service_id).first()
        if not service:
            raise HTTPException(status_code=404, detail="Service not found")
        
        log_sources = db.query(LogSource).filter(
            LogSource.service_id == service_id,
            LogSource.is_active == True
        ).all()
        
        result = []
        for log_source in log_sources:
            config = enhanced_task_config_manager.get_log_source_config(log_source.id)
            config.service_id = service_id  # Ensure service_id is set
            
            result.append(LogSourceTaskResponse(
                log_source_id=log_source.id,
                service_id=service_id,
                service_name=service.name,
                log_source_name=log_source.name,
                fetch_enabled=config.fetch_enabled,
                fetch_interval_minutes=config.fetch_interval_minutes,
                last_fetch_at=config.last_fetch_at,
                last_error=config.last_error,
                modified_at=config.modified_at,
                modified_by=config.modified_by
            ))
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing log source tasks: {e}")
        raise HTTPException(status_code=500, detail="Failed to list log source tasks")

@router.get("/log-sources/{log_source_id}", response_model=LogSourceTaskResponse)
def get_log_source_tasks(log_source_id: str, db: Session = Depends(get_db_dependency)):
    """Get task configuration for a specific log source"""
    try:
        log_source = db.query(LogSource).filter(LogSource.id == log_source_id).first()
        if not log_source:
            raise HTTPException(status_code=404, detail="Log source not found")
        
        service = db.query(Service).filter(Service.id == log_source.service_id).first()
        if not service:
            raise HTTPException(status_code=404, detail="Service not found")
        
        config = enhanced_task_config_manager.get_log_source_config(log_source_id)
        config.service_id = log_source.service_id  # Ensure service_id is set
        
        return LogSourceTaskResponse(
            log_source_id=log_source.id,
            service_id=log_source.service_id,
            service_name=service.name,
            log_source_name=log_source.name,
            fetch_enabled=config.fetch_enabled,
            fetch_interval_minutes=config.fetch_interval_minutes,
            last_fetch_at=config.last_fetch_at,
            last_error=config.last_error,
            modified_at=config.modified_at,
            modified_by=config.modified_by
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting log source tasks: {e}")
        raise HTTPException(status_code=500, detail="Failed to get log source tasks")

@router.put("/log-sources/{log_source_id}", response_model=LogSourceTaskResponse)
def update_log_source_tasks(log_source_id: str, request: LogSourceTaskRequest, db: Session = Depends(get_db_dependency)):
    """Update task configuration for a log source"""
    try:
        log_source = db.query(LogSource).filter(LogSource.id == log_source_id).first()
        if not log_source:
            raise HTTPException(status_code=404, detail="Log source not found")
        
        service = db.query(Service).filter(Service.id == log_source.service_id).first()
        if not service:
            raise HTTPException(status_code=404, detail="Service not found")
        
        config = enhanced_task_config_manager.get_log_source_config(log_source_id)
        config.service_id = log_source.service_id  # Ensure service_id is set
        
        # Update fields if provided
        if request.fetch_enabled is not None:
            config.fetch_enabled = request.fetch_enabled
        if request.fetch_interval_minutes is not None:
            config.fetch_interval_minutes = request.fetch_interval_minutes
        
        config.modified_by = "api"
        
        if not enhanced_task_config_manager.set_log_source_config(config):
            raise HTTPException(status_code=500, detail="Failed to update log source configuration")
        
        return LogSourceTaskResponse(
            log_source_id=log_source.id,
            service_id=log_source.service_id,
            service_name=service.name,
            log_source_name=log_source.name,
            fetch_enabled=config.fetch_enabled,
            fetch_interval_minutes=config.fetch_interval_minutes,
            last_fetch_at=config.last_fetch_at,
            last_error=config.last_error,
            modified_at=config.modified_at,
            modified_by=config.modified_by
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating log source tasks: {e}")
        raise HTTPException(status_code=500, detail="Failed to update log source tasks")

@router.post("/log-sources/{log_source_id}/toggle")
def toggle_log_source_fetch(log_source_id: str, enabled: bool, db: Session = Depends(get_db_dependency)):
    """Enable or disable log fetching for a log source"""
    try:
        log_source = db.query(LogSource).filter(LogSource.id == log_source_id).first()
        if not log_source:
            raise HTTPException(status_code=404, detail="Log source not found")
        
        if enabled:
            success = enhanced_task_config_manager.enable_log_source_fetch(log_source_id, "api")
        else:
            success = enhanced_task_config_manager.disable_log_source_fetch(log_source_id, "api")
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to toggle log source fetch")
        
        return {
            "message": f"Log fetching {'enabled' if enabled else 'disabled'} for {log_source.name}",
            "log_source_id": log_source_id,
            "fetch_enabled": enabled
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling log source fetch: {e}")
        raise HTTPException(status_code=500, detail="Failed to toggle log source fetch")

# ============================================================================
# OVERVIEW AND BULK OPERATIONS
# ============================================================================

@router.get("/overview", response_model=TaskOverviewResponse)
def get_task_overview(db: Session = Depends(get_db_dependency)):
    """Get overview of all task configurations"""
    try:
        # Get service tasks
        service_tasks = list_service_tasks(db)
        
        # Count totals
        total_services = len(service_tasks)
        active_services = sum(1 for s in service_tasks if s.rca_enabled or s.index_code_enabled or s.cleanup_enabled)
        
        total_log_sources = sum(s.log_sources_count for s in service_tasks)
        active_log_sources = sum(s.active_log_sources_count for s in service_tasks)
        
        return TaskOverviewResponse(
            services=service_tasks,
            total_log_sources=total_log_sources,
            active_log_sources=active_log_sources,
            total_services=total_services,
            active_services=active_services
        )
        
    except Exception as e:
        logger.error(f"Error getting task overview: {e}")
        raise HTTPException(status_code=500, detail="Failed to get task overview")

@router.post("/services/{service_id}/enable-all")
def enable_all_service_tasks(service_id: str, db: Session = Depends(get_db_dependency)):
    """Enable all tasks for a service"""
    try:
        service = db.query(Service).filter(Service.id == service_id).first()
        if not service:
            raise HTTPException(status_code=404, detail="Service not found")
        
        # Enable service tasks
        config = enhanced_task_config_manager.get_service_config(service_id)
        config.rca_enabled = True
        config.index_code_enabled = True
        config.cleanup_enabled = True
        config.modified_by = "api"
        
        if not enhanced_task_config_manager.set_service_config(config):
            raise HTTPException(status_code=500, detail="Failed to enable service tasks")
        
        # Enable all log source tasks
        log_sources = db.query(LogSource).filter(
            LogSource.service_id == service_id,
            LogSource.is_active == True
        ).all()
        
        for log_source in log_sources:
            enhanced_task_config_manager.enable_log_source_fetch(log_source.id, "api")
        
        return {
            "message": f"All tasks enabled for service {service.name}",
            "service_id": service_id,
            "log_sources_enabled": len(log_sources)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enabling all service tasks: {e}")
        raise HTTPException(status_code=500, detail="Failed to enable all service tasks")

@router.post("/services/{service_id}/disable-all")
def disable_all_service_tasks(service_id: str, db: Session = Depends(get_db_dependency)):
    """Disable all tasks for a service"""
    try:
        service = db.query(Service).filter(Service.id == service_id).first()
        if not service:
            raise HTTPException(status_code=404, detail="Service not found")
        
        # Disable service tasks
        config = enhanced_task_config_manager.get_service_config(service_id)
        config.rca_enabled = False
        config.index_code_enabled = False
        config.cleanup_enabled = False
        config.modified_by = "api"
        
        if not enhanced_task_config_manager.set_service_config(config):
            raise HTTPException(status_code=500, detail="Failed to disable service tasks")
        
        # Disable all log source tasks
        log_sources = db.query(LogSource).filter(
            LogSource.service_id == service_id,
            LogSource.is_active == True
        ).all()
        
        for log_source in log_sources:
            enhanced_task_config_manager.disable_log_source_fetch(log_source.id, "api")
        
        return {
            "message": f"All tasks disabled for service {service.name}",
            "service_id": service_id,
            "log_sources_disabled": len(log_sources)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disabling all service tasks: {e}")
        raise HTTPException(status_code=500, detail="Failed to disable all service tasks")
