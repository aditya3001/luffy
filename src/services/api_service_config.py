"""
Service Configuration API

This module provides API endpoints for managing service-specific configurations
including Git repositories, processing intervals, and notification settings.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import logging

from ..storage.database import get_db_dependency
from ..storage.models import Service
from .service_scheduler import get_service_scheduler
from .tasks import celery_app

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/services", tags=["service-config"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class ServiceConfigRequest(BaseModel):
    """Request model for service configuration"""
    name: str = Field(..., description="Service name")
    description: Optional[str] = Field(None, description="Service description")
    version: Optional[str] = Field(None, description="Service version")
    
    # Git Configuration
    repository_url: Optional[str] = Field(None, description="Git repository URL")
    git_branch: str = Field("main", description="Git branch to track")
    git_repo_path: Optional[str] = Field(None, description="Local repository path")
    
    # Processing Configuration
    log_processing_enabled: bool = Field(True, description="Master toggle for log processing")
    log_fetch_interval_minutes: int = Field(30, description="Log fetch interval in minutes")
    rca_generation_enabled: bool = Field(True, description="Enable RCA generation")
    rca_generation_interval_minutes: int = Field(15, description="RCA generation interval in minutes")
    code_indexing_enabled: bool = Field(True, description="Enable code indexing")
    code_indexing_interval_hours: int = Field(24, description="Code indexing interval in hours")
    
    # Notification Configuration
    notification_enabled: bool = Field(True, description="Enable notifications")
    notification_webhook_url: Optional[str] = Field(None, description="Webhook URL for notifications")
    notification_email: Optional[str] = Field(None, description="Email for notifications")
    
    is_active: bool = Field(True, description="Service active status")


class ServiceConfigResponse(BaseModel):
    """Response model for service configuration"""
    id: str
    name: str
    description: Optional[str]
    version: Optional[str]
    commit_sha: Optional[str]
    
    # Git Configuration
    repository_url: Optional[str]
    git_branch: str
    git_repo_path: Optional[str]
    
    # Processing Configuration
    log_processing_enabled: bool
    log_fetch_interval_minutes: int
    rca_generation_enabled: bool
    rca_generation_interval_minutes: int
    code_indexing_enabled: bool
    code_indexing_interval_hours: int
    
    # Notification Configuration
    notification_enabled: bool
    notification_webhook_url: Optional[str]
    notification_email: Optional[str]
    
    # Status
    is_active: bool
    last_log_fetch: Optional[str]
    last_rca_generation: Optional[str]
    last_code_indexing: Optional[str]
    
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class ServiceStatusResponse(BaseModel):
    """Response model for service status"""
    service_id: str
    service_name: str
    is_active: bool
    last_log_fetch: Optional[str]
    last_rca_generation: Optional[str]
    last_code_indexing: Optional[str]
    log_sources_count: int
    active_log_sources: int
    configuration: Dict[str, Any]


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.get("/{service_id}/config", response_model=ServiceConfigResponse)
async def get_service_config(
    service_id: str,
    db: Session = Depends(get_db_dependency)
):
    """Get configuration for a specific service"""
    try:
        service = db.query(Service).filter(Service.id == service_id).first()
        if not service:
            raise HTTPException(status_code=404, detail="Service not found")
        
        return ServiceConfigResponse(
            id=service.id,
            name=service.name,
            description=service.description,
            version=service.version,
            commit_sha=service.commit_sha,
            repository_url=service.repository_url,
            git_branch=service.git_branch,
            git_repo_path=service.git_repo_path,
            log_fetch_interval_minutes=service.log_fetch_interval_minutes,
            rca_generation_enabled=service.rca_generation_enabled,
            rca_generation_interval_minutes=service.rca_generation_interval_minutes,
            code_indexing_enabled=service.code_indexing_enabled,
            code_indexing_interval_hours=service.code_indexing_interval_hours,
            notification_enabled=service.notification_enabled,
            notification_webhook_url=service.notification_webhook_url,
            notification_email=service.notification_email,
            is_active=service.is_active,
            last_log_fetch=service.last_log_fetch.isoformat() if service.last_log_fetch else None,
            last_rca_generation=service.last_rca_generation.isoformat() if service.last_rca_generation else None,
            last_code_indexing=service.last_code_indexing.isoformat() if service.last_code_indexing else None,
            created_at=service.created_at.isoformat(),
            updated_at=service.updated_at.isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting service config: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{service_id}/config", response_model=ServiceConfigResponse)
async def update_service_config(
    service_id: str,
    config: ServiceConfigRequest,
    db: Session = Depends(get_db_dependency)
):
    """Update configuration for a specific service"""
    try:
        service = db.query(Service).filter(Service.id == service_id).first()
        if not service:
            raise HTTPException(status_code=404, detail="Service not found")
        
        # Update service configuration
        for field, value in config.dict(exclude_unset=True).items():
            setattr(service, field, value)
        
        db.commit()
        db.refresh(service)
        
        logger.info(f"Updated configuration for service: {service.name}")
        
        return ServiceConfigResponse(
            id=service.id,
            name=service.name,
            description=service.description,
            version=service.version,
            commit_sha=service.commit_sha,
            repository_url=service.repository_url,
            git_branch=service.git_branch,
            git_repo_path=service.git_repo_path,
            log_fetch_interval_minutes=service.log_fetch_interval_minutes,
            rca_generation_enabled=service.rca_generation_enabled,
            rca_generation_interval_minutes=service.rca_generation_interval_minutes,
            code_indexing_enabled=service.code_indexing_enabled,
            code_indexing_interval_hours=service.code_indexing_interval_hours,
            notification_enabled=service.notification_enabled,
            notification_webhook_url=service.notification_webhook_url,
            notification_email=service.notification_email,
            is_active=service.is_active,
            last_log_fetch=service.last_log_fetch.isoformat() if service.last_log_fetch else None,
            last_rca_generation=service.last_rca_generation.isoformat() if service.last_rca_generation else None,
            last_code_indexing=service.last_code_indexing.isoformat() if service.last_code_indexing else None,
            created_at=service.created_at.isoformat(),
            updated_at=service.updated_at.isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating service config: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{service_id}/status", response_model=ServiceStatusResponse)
async def get_service_status(
    service_id: str,
    db: Session = Depends(get_db_dependency)
):
    """Get detailed status for a specific service"""
    try:
        scheduler = get_service_scheduler(celery_app)
        status = scheduler.get_service_status(service_id)
        
        if 'error' in status:
            raise HTTPException(status_code=404, detail=status['error'])
        
        return ServiceStatusResponse(**status)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting service status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/status", response_model=List[ServiceStatusResponse])
async def get_all_services_status():
    """Get status for all services"""
    try:
        scheduler = get_service_scheduler(celery_app)
        statuses = scheduler.get_all_services_status()
        
        return [ServiceStatusResponse(**status) for status in statuses if 'error' not in status]
        
    except Exception as e:
        logger.error(f"Error getting all services status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{service_id}/trigger-log-fetch")
async def trigger_log_fetch(
    service_id: str,
    db: Session = Depends(get_db_dependency)
):
    """Manually trigger log fetch for a specific service"""
    try:
        # Verify service exists
        service = db.query(Service).filter(Service.id == service_id).first()
        if not service:
            raise HTTPException(status_code=404, detail="Service not found")
        
        # Import and trigger the task
        from .tasks import fetch_and_process_logs
        task = fetch_and_process_logs.delay(service_id=service_id)
        
        return {
            "message": f"Log fetch triggered for service {service.name}",
            "task_id": task.id,
            "service_id": service_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering log fetch: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{service_id}/trigger-rca")
async def trigger_rca_generation(
    service_id: str,
    db: Session = Depends(get_db_dependency)
):
    """Manually trigger RCA generation for a specific service"""
    try:
        # Verify service exists
        service = db.query(Service).filter(Service.id == service_id).first()
        if not service:
            raise HTTPException(status_code=404, detail="Service not found")
        
        # Import and trigger the task
        from .tasks import generate_rca_for_clusters
        task = generate_rca_for_clusters.delay(service_id=service_id)
        
        return {
            "message": f"RCA generation triggered for service {service.name}",
            "task_id": task.id,
            "service_id": service_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering RCA generation: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{service_id}/trigger-code-indexing")
async def trigger_code_indexing(
    service_id: str,
    db: Session = Depends(get_db_dependency)
):
    """Manually trigger code indexing for a specific service"""
    try:
        # Verify service exists
        service = db.query(Service).filter(Service.id == service_id).first()
        if not service:
            raise HTTPException(status_code=404, detail="Service not found")
        
        if not service.repository_url or not service.git_repo_path:
            raise HTTPException(
                status_code=400, 
                detail="Service must have repository_url and git_repo_path configured"
            )
        
        # Import and trigger the task
        from .tasks import index_code_repository
        task = index_code_repository.delay(
            service_id=service_id,
            repository_path=service.git_repo_path,
            branch=service.git_branch
        )
        
        return {
            "message": f"Code indexing triggered for service {service.name}",
            "task_id": task.id,
            "service_id": service_id,
            "repository_path": service.git_repo_path,
            "branch": service.git_branch
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering code indexing: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{service_id}/toggle-log-processing")
async def toggle_log_processing(
    service_id: str,
    enabled: bool = Query(..., description="Enable or disable log processing"),
    db: Session = Depends(get_db_dependency)
):
    """
    Toggle log processing on/off for a specific service.
    
    When disabled, the periodic log fetch task will skip this service.
    RCA and code indexing can still be triggered manually.
    """
    try:
        # Verify service exists
        service = db.query(Service).filter(Service.id == service_id).first()
        if not service:
            raise HTTPException(status_code=404, detail=f"Service '{service_id}' not found")
        
        # Log current state
        logger.info(f"Current log_processing_enabled for {service.name}: {service.log_processing_enabled}")
        
        # Update the toggle
        service.log_processing_enabled = enabled
        db.commit()
        db.refresh(service)  # Refresh to ensure we have latest state
        
        # Verify the update
        logger.info(f"Updated log_processing_enabled for {service.name}: {service.log_processing_enabled}")
        
        status = "enabled" if enabled else "disabled"
        
        return {
            "message": f"Log processing {status} for service {service.name}",
            "service_id": service_id,
            "service_name": service.name,
            "log_processing_enabled": service.log_processing_enabled  # Return actual DB value
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling log processing for service {service_id}: {e}")
        logger.exception(e)  # Log full traceback
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
