"""
FastAPI router for service and log source management.
Provides endpoints for managing services and their log sources.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
import logging
from sqlalchemy.orm import Session
from src.storage.database import get_db_dependency
from src.storage.models import Service, LogSource, ExceptionCluster
from src.ingestion.opensearch_connector import OpenSearchConnector

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["services"])

# Request/Response Models
class ServiceRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    version: Optional[str] = Field(None, max_length=50)
    repository_url: Optional[str] = None
    git_provider: Optional[str] = Field(None, pattern="^(github|gitlab)$")  # github, gitlab (bitbucket not yet implemented)
    git_branch: Optional[str] = Field(None, max_length=100)
    git_repo_path: Optional[str] = None  # Optional: only needed for local cloning
    access_token: Optional[str] = None  # GitHub/GitLab/Bitbucket personal access token
    use_api_mode: Optional[bool] = False  # True: API mode (in-memory), False: Local mode (clone to disk)

class ServiceResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    version: Optional[str]
    repository_url: Optional[str]
    git_provider: Optional[str]
    git_branch: Optional[str]
    git_repo_path: Optional[str]
    access_token: Optional[str]
    use_api_mode: Optional[bool]
    log_processing_enabled: Optional[bool]
    is_active: bool
    log_sources_count: int
    active_exceptions_count: int
    created_at: datetime
    updated_at: datetime

class LogSourceRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    source_type: str = Field(..., pattern="^(opensearch|elasticsearch|loki|cloudwatch|splunk)$")
    host: str = Field(..., min_length=1)
    port: int = Field(default=9200, ge=1, le=65535)
    username: Optional[str] = None
    password: Optional[str] = None
    use_ssl: bool = True
    verify_certs: bool = True
    index_pattern: str = Field(..., min_length=1)
    query_filter: Optional[Dict[str, Any]] = None
    fetch_enabled: bool = True
    fetch_interval_minutes: int = Field(default=30, ge=1, le=1440)

class LogSourceResponse(BaseModel):
    id: str
    service_id: str
    name: str
    source_type: str
    host: str
    port: int
    username: Optional[str]
    use_ssl: Optional[bool] = False
    verify_certs: Optional[bool] = False
    index_pattern: str
    query_filter: Optional[Dict[str, Any]]
    is_active: bool
    fetch_enabled: bool
    fetch_interval_minutes: int
    connection_status: str
    last_connection_test: Optional[datetime]
    last_fetch_at: Optional[datetime]
    last_error: Optional[str]
    active_exceptions_count: int
    created_at: datetime
    updated_at: datetime

class LogSourceUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    host: Optional[str] = Field(None, min_length=1)
    port: Optional[int] = Field(None, ge=1, le=65535)
    username: Optional[str] = None
    password: Optional[str] = None
    use_ssl: Optional[bool] = None
    verify_certs: Optional[bool] = None
    index_pattern: Optional[str] = Field(None, min_length=1)
    query_filter: Optional[Dict[str, Any]] = None
    fetch_enabled: Optional[bool] = None
    fetch_interval_minutes: Optional[int] = Field(None, ge=1, le=1440)

class ConnectionTestResponse(BaseModel):
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None

# ============================================================================
# SERVICE ENDPOINTS
# ============================================================================

@router.get("/services", response_model=List[ServiceResponse])
def list_services(db: Session = Depends(get_db_dependency)):
    """List all services with their statistics"""
    try:
        services = db.query(Service).filter(Service.is_active == True).all()
        
        result = []
        for service in services:
            # Count log sources
            log_sources_count = db.query(LogSource).filter(
                LogSource.service_id == service.id,
                LogSource.is_active == True
            ).count()
            
            # Count active exceptions
            active_exceptions_count = db.query(ExceptionCluster).filter(
                ExceptionCluster.service_id == service.id,
                ExceptionCluster.status == 'active'
            ).count()
            
            result.append(ServiceResponse(
                id=service.id,
                name=service.name,
                description=service.description,
                version=service.version,
                repository_url=service.repository_url,
                git_provider=service.git_provider,
                git_branch=service.git_branch,
                git_repo_path=service.git_repo_path,
                access_token=service.access_token,
                use_api_mode=service.use_api_mode or False,
                is_active=service.is_active,
                log_sources_count=log_sources_count,
                active_exceptions_count=active_exceptions_count,
                log_processing_enabled=service.log_processing_enabled,
                created_at=service.created_at,
                updated_at=service.updated_at
            ))
        
        return result
        
    except Exception as e:
        logger.error(f"Error listing services: {e}")
        raise HTTPException(status_code=500, detail="Failed to list services")

@router.post("/services", response_model=ServiceResponse)
def create_service(request: ServiceRequest, db: Session = Depends(get_db_dependency)):
    """Create a new service"""
    try:
        # Check if service name already exists
        existing = db.query(Service).filter(Service.name == request.name).first()
        if existing:
            raise HTTPException(status_code=400, detail="Service name already exists")
        
        # Create new service
        service = Service(
            id=str(uuid.uuid4()),
            name=request.name,
            description=request.description,
            version=request.version,
            repository_url=request.repository_url,
            git_provider=request.git_provider,
            git_branch=request.git_branch,
            git_repo_path=request.git_repo_path,
            access_token=request.access_token,
            use_api_mode=request.use_api_mode if request.use_api_mode is not None else False,
            log_processing_enabled=True,
            is_active=True
        )
        
        db.add(service)
        db.commit()
        db.refresh(service)
        
        return ServiceResponse(
            id=service.id,
            name=service.name,
            description=service.description,
            version=service.version,
            repository_url=service.repository_url,
            git_provider=service.git_provider,
            git_branch=service.git_branch,
            git_repo_path=service.git_repo_path,
            access_token=service.access_token,
            use_api_mode=service.use_api_mode or False,
            log_processing_enabled=service.log_processing_enabled or True,
            is_active=service.is_active,
            log_sources_count=0,
            active_exceptions_count=0,
            created_at=service.created_at,
            updated_at=service.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating service: {e}")
        raise HTTPException(status_code=500, detail="Failed to create service")

@router.get("/services/{service_id}", response_model=ServiceResponse)
def get_service(service_id: str, db: Session = Depends(get_db_dependency)):
    """Get service details"""
    try:
        service = db.query(Service).filter(Service.id == service_id).first()
        if not service:
            raise HTTPException(status_code=404, detail="Service not found")
        
        # Count log sources and active exceptions
        log_sources_count = db.query(LogSource).filter(
            LogSource.service_id == service.id,
            LogSource.is_active == True
        ).count()
        
        active_exceptions_count = db.query(ExceptionCluster).filter(
            ExceptionCluster.service_id == service.id,
            ExceptionCluster.status == 'active'
        ).count()
        
        return ServiceResponse(
            id=service.id,
            name=service.name,
            description=service.description,
            version=service.version,
            repository_url=service.repository_url,
            git_provider=service.git_provider,
            git_branch=service.git_branch,
            git_repo_path=service.git_repo_path,
            access_token=service.access_token,
            use_api_mode=service.use_api_mode or False,
            is_active=service.is_active,
            log_sources_count=log_sources_count,
            active_exceptions_count=active_exceptions_count,
            log_processing_enabled=service.log_processing_enabled,
            created_at=service.created_at,
            updated_at=service.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting service: {e}")
        raise HTTPException(status_code=500, detail="Failed to get service")

@router.put("/services/{service_id}", response_model=ServiceResponse)
def update_service(service_id: str, request: ServiceRequest, db: Session = Depends(get_db_dependency)):
    """Update service details"""
    try:
        service = db.query(Service).filter(Service.id == service_id).first()
        if not service:
            raise HTTPException(status_code=404, detail="Service not found")
        
        # Check if new name conflicts with existing service
        if request.name != service.name:
            existing = db.query(Service).filter(
                Service.name == request.name,
                Service.id != service_id
            ).first()
            if existing:
                raise HTTPException(status_code=400, detail="Service name already exists")
        
        # Update service
        service.name = request.name
        service.description = request.description
        service.version = request.version
        service.repository_url = request.repository_url
        service.git_provider = request.git_provider
        service.git_branch = request.git_branch
        service.git_repo_path = request.git_repo_path
        service.access_token = request.access_token
        service.use_api_mode = request.use_api_mode if request.use_api_mode is not None else False
        service.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(service)
        
        # Get counts
        log_sources_count = db.query(LogSource).filter(
            LogSource.service_id == service.id,
            LogSource.is_active == True
        ).count()
        
        active_exceptions_count = db.query(ExceptionCluster).filter(
            ExceptionCluster.service_id == service.id,
            ExceptionCluster.status == 'active'
        ).count()
        
        return ServiceResponse(
            id=service.id,
            name=service.name,
            description=service.description,
            version=service.version,
            repository_url=service.repository_url,
            git_provider=service.git_provider,
            git_branch=service.git_branch,
            git_repo_path=service.git_repo_path,
            access_token=service.access_token,
            use_api_mode=service.use_api_mode or False,
            is_active=service.is_active,
            log_processing_enabled=service.log_processing_enabled,
            log_sources_count=log_sources_count,
            active_exceptions_count=active_exceptions_count,
            created_at=service.created_at,
            updated_at=service.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating service: {e}")
        raise HTTPException(status_code=500, detail="Failed to update service")

@router.delete("/services/{service_id}")
def delete_service(service_id: str, db: Session = Depends(get_db_dependency)):
    """Delete a service (soft delete)"""
    try:
        service = db.query(Service).filter(Service.id == service_id).first()
        if not service:
            raise HTTPException(status_code=404, detail="Service not found")
        
        # Check if service has active exceptions
        active_exceptions = db.query(ExceptionCluster).filter(
            ExceptionCluster.service_id == service_id,
            ExceptionCluster.status == 'active'
        ).count()
        
        if active_exceptions > 0:
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot delete service with {active_exceptions} active exceptions"
            )
        
        # Soft delete
        service.is_active = False
        service.updated_at = datetime.utcnow()
        
        # Deactivate all log sources
        db.query(LogSource).filter(LogSource.service_id == service_id).update({
            "is_active": False,
            "updated_at": datetime.utcnow()
        })
        
        db.commit()
        
        return {"message": "Service deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting service: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete service")

# ============================================================================
# LOG SOURCE ENDPOINTS
# ============================================================================

@router.get("/services/{service_id}/log-sources", response_model=List[LogSourceResponse])
def list_log_sources(service_id: str, db: Session = Depends(get_db_dependency)):
    """List log sources for a service"""
    try:
        # Verify service exists
        service = db.query(Service).filter(Service.id == service_id).first()
        if not service:
            raise HTTPException(status_code=404, detail="Service not found")
        
        log_sources = db.query(LogSource).filter(
            LogSource.service_id == service_id,
            LogSource.is_active == True
        ).all()
        
        result = []
        for source in log_sources:
            # Count active exceptions for this log source
            active_exceptions_count = db.query(ExceptionCluster).filter(
                ExceptionCluster.log_source_id == source.id,
                ExceptionCluster.status == 'active'
            ).count()
            
            result.append(LogSourceResponse(
                id=source.id,
                service_id=source.service_id,
                name=source.name,
                source_type=source.source_type,
                host=source.host,
                port=source.port,
                username=source.username,
                use_ssl=source.use_ssl,
                verify_certs=source.verify_certs,
                index_pattern=source.index_pattern,
                query_filter=source.query_filter,
                is_active=source.is_active,
                fetch_enabled=source.fetch_enabled,
                fetch_interval_minutes=source.fetch_interval_minutes,
                connection_status=source.connection_status,
                last_connection_test=source.last_connection_test,
                last_fetch_at=source.last_fetch_at,
                last_error=source.last_error,
                active_exceptions_count=active_exceptions_count,
                created_at=source.created_at,
                updated_at=source.updated_at
            ))
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing log sources: {e}")
        raise HTTPException(status_code=500, detail="Failed to list log sources")

@router.post("/services/{service_id}/log-sources", response_model=LogSourceResponse)
def create_log_source(service_id: str, request: LogSourceRequest, db: Session = Depends(get_db_dependency)):
    """Create a new log source for a service"""
    try:
        # Verify service exists
        service = db.query(Service).filter(Service.id == service_id).first()
        if not service:
            raise HTTPException(status_code=404, detail="Service not found")
        
        # Check if log source name already exists for this service
        existing = db.query(LogSource).filter(
            LogSource.service_id == service_id,
            LogSource.name == request.name
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Log source name already exists for this service")
        
        # Create new log source
        log_source = LogSource(
            id=str(uuid.uuid4()),
            service_id=service_id,
            name=request.name,
            source_type=request.source_type,
            host=request.host,
            port=request.port,
            username=request.username,
            password=request.password,
            use_ssl=request.use_ssl,
            verify_certs=request.verify_certs,
            index_pattern=request.index_pattern,
            query_filter=request.query_filter,
            is_active=True,
            fetch_enabled=request.fetch_enabled,
            fetch_interval_minutes=request.fetch_interval_minutes,
            connection_status='unknown'
        )
        
        db.add(log_source)
        db.commit()
        db.refresh(log_source)
        
        return LogSourceResponse(
            id=log_source.id,
            service_id=log_source.service_id,
            name=log_source.name,
            source_type=log_source.source_type,
            host=log_source.host,
            port=log_source.port,
            username=log_source.username,
            use_ssl=log_source.use_ssl,
            verify_certs=log_source.verify_certs,
            index_pattern=log_source.index_pattern,
            query_filter=log_source.query_filter,
            is_active=log_source.is_active,
            fetch_enabled=log_source.fetch_enabled,
            fetch_interval_minutes=log_source.fetch_interval_minutes,
            connection_status=log_source.connection_status,
            last_connection_test=log_source.last_connection_test,
            last_fetch_at=log_source.last_fetch_at,
            last_error=log_source.last_error,
            active_exceptions_count=0,
            created_at=log_source.created_at,
            updated_at=log_source.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating log source: {e}")
        raise HTTPException(status_code=500, detail="Failed to create log source")

@router.put("/services/{service_id}/log-sources/{log_source_id}", response_model=LogSourceResponse)
def update_log_source(
    service_id: str, 
    log_source_id: str, 
    request: LogSourceUpdateRequest, 
    db: Session = Depends(get_db_dependency)
):
    """Update log source configuration"""
    try:
        log_source = db.query(LogSource).filter(
            LogSource.id == log_source_id,
            LogSource.service_id == service_id
        ).first()
        
        if not log_source:
            raise HTTPException(status_code=404, detail="Log source not found")
        
        # Update fields if provided
        if request.name is not None:
            # Check name uniqueness
            existing = db.query(LogSource).filter(
                LogSource.service_id == service_id,
                LogSource.name == request.name,
                LogSource.id != log_source_id
            ).first()
            if existing:
                raise HTTPException(status_code=400, detail="Log source name already exists for this service")
            log_source.name = request.name
        
        if request.host is not None:
            log_source.host = request.host
        if request.port is not None:
            log_source.port = request.port
        if request.username is not None:
            log_source.username = request.username
        if request.password is not None:
            log_source.password = request.password
        if request.use_ssl is not None:
            log_source.use_ssl = request.use_ssl
        if request.verify_certs is not None:
            log_source.verify_certs = request.verify_certs
        if request.index_pattern is not None:
            log_source.index_pattern = request.index_pattern
        if request.query_filter is not None:
            log_source.query_filter = request.query_filter
        if request.fetch_enabled is not None:
            log_source.fetch_enabled = request.fetch_enabled
        if request.fetch_interval_minutes is not None:
            log_source.fetch_interval_minutes = request.fetch_interval_minutes
        
        log_source.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(log_source)
        
        # Get active exceptions count
        active_exceptions_count = db.query(ExceptionCluster).filter(
            ExceptionCluster.log_source_id == log_source.id,
            ExceptionCluster.status == 'active'
        ).count()
        
        return LogSourceResponse(
            id=log_source.id,
            service_id=log_source.service_id,
            name=log_source.name,
            source_type=log_source.source_type,
            host=log_source.host,
            port=log_source.port,
            username=log_source.username,
            use_ssl=log_source.use_ssl,
            verify_certs=log_source.verify_certs,
            index_pattern=log_source.index_pattern,
            query_filter=log_source.query_filter,
            is_active=log_source.is_active,
            fetch_enabled=log_source.fetch_enabled,
            fetch_interval_minutes=log_source.fetch_interval_minutes,
            connection_status=log_source.connection_status,
            last_connection_test=log_source.last_connection_test,
            last_fetch_at=log_source.last_fetch_at,
            last_error=log_source.last_error,
            active_exceptions_count=active_exceptions_count,
            created_at=log_source.created_at,
            updated_at=log_source.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating log source: {e}")
        raise HTTPException(status_code=500, detail="Failed to update log source")

@router.delete("/services/{service_id}/log-sources/{log_source_id}")
def delete_log_source(service_id: str, log_source_id: str, db: Session = Depends(get_db_dependency)):
    """Delete a log source (soft delete)"""
    try:
        log_source = db.query(LogSource).filter(
            LogSource.id == log_source_id,
            LogSource.service_id == service_id
        ).first()
        
        if not log_source:
            raise HTTPException(status_code=404, detail="Log source not found")
        
        # Check if log source has active exceptions
        active_exceptions = db.query(ExceptionCluster).filter(
            ExceptionCluster.log_source_id == log_source_id,
            ExceptionCluster.status == 'active'
        ).count()
        
        if active_exceptions > 0:
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot delete log source with {active_exceptions} active exceptions"
            )
        
        # Soft delete
        log_source.is_active = False
        log_source.updated_at = datetime.utcnow()
        
        db.commit()
        
        return {"message": "Log source deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting log source: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete log source")

@router.post("/services/{service_id}/log-sources/{log_source_id}/test", response_model=ConnectionTestResponse)
def test_log_source_connection(service_id: str, log_source_id: str, db: Session = Depends(get_db_dependency)):
    """Test connection to a log source"""
    try:
        log_source = db.query(LogSource).filter(
            LogSource.id == log_source_id,
            LogSource.service_id == service_id
        ).first()
        
        if not log_source:
            raise HTTPException(status_code=404, detail="Log source not found")
        
        # Test connection based on source type
        if log_source.source_type in ['opensearch', 'elasticsearch']:
            connector = OpenSearchConnector(
                host=log_source.host,
                port=log_source.port,
                username=log_source.username,
                password=log_source.password,
                use_ssl=log_source.use_ssl,
                verify_certs=log_source.verify_certs
            )
            
            success, message, details = connector.test_connection()
            
            # Update connection status
            log_source.connection_status = 'connected' if success else 'error'
            log_source.last_connection_test = datetime.utcnow()
            if not success:
                log_source.last_error = message
            else:
                log_source.last_error = None
            
            db.commit()
            
            return ConnectionTestResponse(
                success=success,
                message=message,
                details=details
            )
        else:
            # For other source types, return not implemented
            return ConnectionTestResponse(
                success=False,
                message=f"Connection test not implemented for {log_source.source_type}",
                details={"source_type": log_source.source_type}
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing log source connection: {e}")
        raise HTTPException(status_code=500, detail="Failed to test connection")

@router.post("/services/{service_id}/log-sources/{log_source_id}/toggle")
def toggle_log_source_fetch(service_id: str, log_source_id: str, enabled: bool, db: Session = Depends(get_db_dependency)):
    """Enable or disable log fetching for a log source"""
    try:
        log_source = db.query(LogSource).filter(
            LogSource.id == log_source_id,
            LogSource.service_id == service_id
        ).first()
        
        if not log_source:
            raise HTTPException(status_code=404, detail="Log source not found")
        
        log_source.fetch_enabled = enabled
        log_source.updated_at = datetime.utcnow()
        
        db.commit()
        
        return {
            "message": f"Log fetching {'enabled' if enabled else 'disabled'} for {log_source.name}",
            "fetch_enabled": enabled
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling log source fetch: {e}")
        raise HTTPException(status_code=500, detail="Failed to toggle log source fetch")
