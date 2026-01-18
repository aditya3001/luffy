"""
Code Indexing API Endpoints

Provides REST API endpoints for managing code indexing:
- Manual trigger for code indexing
- Get indexing status
- View indexing history
"""
import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from src.storage.database import get_db_dependency
from src.storage.models import Service
from src.services.tasks import index_code_repository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/code-indexing", tags=["code-indexing"])


@router.post("/services/{service_id}/trigger")
async def trigger_code_indexing(
    service_id: str,
    force_full: bool = False,
    auto_sync: bool = True,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db_dependency)
):
    """
    Manually trigger code indexing for a service.
    
    Args:
        service_id: Service ID to index
        force_full: Force full indexing (default: incremental)
         auto_sync: Automatically sync repository with remote before indexing (default: True)
    
    Returns:
        Task information
    """
    logger.info("indexing code")

    # Validate service exists
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    # Check if already indexing
    if service.code_indexing_status == 'indexing':
        raise HTTPException(
            status_code=409,
            detail="Code indexing already in progress for this service"
        )
    # Trigger indexing task
    task = index_code_repository.apply_async(
        kwargs={
            'service_id': service_id,
            'trigger_reason': 'manual',
            'force_full': force_full
        }
    )
    
    logger.info(f"Manually triggered code indexing for service {service_id} (task_id: {task.id}, auto_sync: {auto_sync})")
    
    return {
        "message": "Code indexing triggered successfully",
        "service_id": service_id,
        "task_id": task.id,
        "force_full": force_full,
        "auto_sync": auto_sync,
        "trigger_reason": "manual"
    }


@router.get("/services/{service_id}/status")
async def get_indexing_status(
    service_id: str,
    db: Session = Depends(get_db_dependency)
):
    """
    Get code indexing status for a service.
    
    Args:
        service_id: Service ID
    
    Returns:
        Indexing status information
    """
    logger.info("fetching service status")
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    return {
        "service_id": service_id,
        "service_name": service.name,
        "status": service.code_indexing_status or 'not_indexed',
        "last_indexed_at": service.last_code_indexing.isoformat() if service.last_code_indexing else None,
        "last_indexed_commit": service.last_indexed_commit,
        "indexing_trigger": service.code_indexing_trigger,
        "indexing_error": service.code_indexing_error,
        "git_repo_path": service.git_repo_path,
        "git_branch": service.git_branch,
        "code_indexing_enabled": service.code_indexing_enabled
    }


@router.get("/services/{service_id}/history")
async def get_indexing_history(
    service_id: str,
    limit: int = 10,
    db: Session = Depends(get_db_dependency)
):
    """
    Get code indexing history for a service.
    
    Args:
        service_id: Service ID
        limit: Maximum number of records to return
    
    Returns:
        List of indexing history records
    """
    from src.storage.models import IndexingMetadata
    
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    # Get indexing metadata records
    metadata_records = db.query(IndexingMetadata).filter(
        IndexingMetadata.repository == service.name
    ).order_by(
        IndexingMetadata.last_indexed_at.desc()
    ).limit(limit).all()
    
    history = []
    for record in metadata_records:
        history.append({
            "repository": record.repository,
            "last_indexed_commit": record.last_indexed_commit,
            "last_indexed_at": record.last_indexed_at.isoformat() if record.last_indexed_at else None,
            "total_files_indexed": record.total_files_indexed,
            "total_blocks_indexed": record.total_blocks_indexed,
            "indexing_mode": record.indexing_mode
        })
    
    return {
        "service_id": service_id,
        "service_name": service.name,
        "history": history,
        "total_records": len(history)
    }


@router.post("/services/{service_id}/enable")
async def enable_code_indexing(
    service_id: str,
    db: Session = Depends(get_db_dependency)
):
    """
    Enable code indexing for a service.
    
    Args:
        service_id: Service ID
    
    Returns:
        Success message
    """
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    service.code_indexing_enabled = True
    db.commit()
    
    logger.info(f"Enabled code indexing for service {service_id}")
    
    return {
        "message": "Code indexing enabled successfully",
        "service_id": service_id,
        "code_indexing_enabled": True
    }


@router.post("/services/{service_id}/disable")
async def disable_code_indexing(
    service_id: str,
    db: Session = Depends(get_db_dependency)
):
    """
    Disable code indexing for a service.
    
    Args:
        service_id: Service ID
    
    Returns:
        Success message
    """
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    service.code_indexing_enabled = False
    db.commit()
    
    logger.info(f"Disabled code indexing for service {service_id}")
    
    return {
        "message": "Code indexing disabled successfully",
        "service_id": service_id,
        "code_indexing_enabled": False
    }


@router.get("/status/all")
async def get_all_indexing_status(
    db: Session = Depends(get_db_dependency)
):
    """
    Get code indexing status for all services.
    
    Returns:
        List of all services with their indexing status
    """
    services = db.query(Service).filter(Service.is_active == True).all()
    
    status_list = []
    for service in services:
        status_list.append({
            "service_id": service.id,
            "service_name": service.name,
            "status": service.code_indexing_status or 'not_indexed',
            "last_indexed_at": service.last_code_indexing.isoformat() if service.last_code_indexing else None,
            "last_indexed_commit": service.last_indexed_commit,
            "indexing_enabled": service.code_indexing_enabled,
            "git_repo_path": service.git_repo_path,
            "git_branch": service.git_branch
        })
    
    return {
        "services": status_list,
        "total_services": len(status_list)
    }
