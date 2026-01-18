"""
Dedicated Log Source Management API.
Provides simplified endpoints for log source configuration and monitoring control.
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
import logging
from sqlalchemy.orm import Session
from src.storage.database import get_db_dependency
from src.storage.models import Service, LogSource, ExceptionCluster
from src.ingestion.opensearch_connector import OpenSearchConnector
from src.services.task_config_enhanced import enhanced_task_config_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/log-sources", tags=["log-sources"])

# Request/Response Models
class LogSourceConfigRequest(BaseModel):
    """Request model for creating/updating log source configuration"""
    name: str = Field(..., min_length=1, max_length=100, description="Display name for the log source")
    service_id: str = Field(..., description="ID of the service this log source belongs to")
    source_type: str = Field(..., pattern="^(opensearch|elasticsearch|loki|cloudwatch|splunk)$", description="Type of log source")
    
    # Connection settings
    host: str = Field(..., min_length=1, description="Hostname or IP address")
    port: int = Field(default=9200, ge=1, le=65535, description="Port number")
    username: Optional[str] = Field(None, description="Username for authentication")
    password: Optional[str] = Field(None, description="Password for authentication")
    use_ssl: bool = Field(default=True, description="Use SSL/TLS connection")
    verify_certs: bool = Field(default=True, description="Verify SSL certificates")
    
    # Index/Query settings
    index_pattern: str = Field(..., min_length=1, description="Index pattern to search (e.g., logs-*)")
    query_filter: Optional[Dict[str, Any]] = Field(None, description="Additional query filters")
    
    # Monitoring settings
    fetch_enabled: bool = Field(default=True, description="Enable automatic log fetching")
    fetch_interval_minutes: int = Field(default=30, ge=1, le=1440, description="Fetch interval in minutes")

class LogSourceResponse(BaseModel):
    """Response model for log source information"""
    id: str
    name: str
    service_id: str
    service_name: str
    source_type: str
    host: str
    port: int
    username: Optional[str]
    use_ssl: bool
    verify_certs: bool
    index_pattern: str
    query_filter: Optional[Dict[str, Any]]
    is_active: bool
    fetch_enabled: bool
    fetch_interval_minutes: int
    connection_status: str  # connected, disconnected, error, unknown
    last_connection_test: Optional[datetime]
    last_fetch_at: Optional[datetime]
    last_error: Optional[str]
    active_exceptions_count: int
    created_at: datetime
    updated_at: datetime

class LogSourceUpdateRequest(BaseModel):
    """Request model for updating log source configuration"""
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
    """Response model for connection test results"""
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None
    response_time_ms: Optional[int] = None

class MonitoringControlRequest(BaseModel):
    """Request model for monitoring control"""
    enabled: bool
    apply_to_all: bool = Field(default=False, description="Apply to all log sources in service")

class MonitoringStatusResponse(BaseModel):
    """Response model for monitoring status"""
    log_source_id: str
    log_source_name: str
    service_id: str
    service_name: str
    monitoring_enabled: bool
    fetch_enabled: bool
    connection_status: str
    last_fetch_at: Optional[datetime]
    next_fetch_at: Optional[datetime]
    fetch_interval_minutes: int

# ============================================================================
# LOG SOURCE CRUD OPERATIONS
# ============================================================================

@router.get("", response_model=List[LogSourceResponse])
def list_all_log_sources(db: Session = Depends(get_db_dependency)):
    """List all log sources across all services"""
    try:
        log_sources = db.query(LogSource).join(Service).filter(
            LogSource.is_active == True,
            Service.is_active == True
        ).all()
        
        result = []
        for log_source in log_sources:
            # Count active exceptions for this log source
            active_exceptions = db.query(ExceptionCluster).filter(
                ExceptionCluster.log_source_id == log_source.id,
                ExceptionCluster.status == 'active'
            ).count()
            
            result.append(LogSourceResponse(
                id=log_source.id,
                name=log_source.name,
                service_id=log_source.service_id,
                service_name=log_source.service.name,
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
                active_exceptions_count=active_exceptions,
                created_at=log_source.created_at,
                updated_at=log_source.updated_at
            ))
        
        return result
        
    except Exception as e:
        logger.error(f"Error listing log sources: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list log sources")

@router.post("", response_model=LogSourceResponse)
def create_log_source(request: LogSourceConfigRequest, db: Session = Depends(get_db_dependency)):
    """Create a new log source"""
    try:
        # Verify service exists
        service = db.query(Service).filter(
            Service.id == request.service_id,
            Service.is_active == True
        ).first()
        
        if not service:
            raise HTTPException(status_code=404, detail="Service not found")
        
        # Check for duplicate name within service
        existing = db.query(LogSource).filter(
            LogSource.service_id == request.service_id,
            LogSource.name == request.name,
            LogSource.is_active == True
        ).first()
        
        if existing:
            raise HTTPException(status_code=400, detail="Log source name already exists in this service")
        
        # Create new log source
        log_source = LogSource(
            id=str(uuid.uuid4()),
            service_id=request.service_id,
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
            fetch_enabled=request.fetch_enabled,
            fetch_interval_minutes=request.fetch_interval_minutes,
            is_active=True,
            connection_status='unknown'
        )
        
        db.add(log_source)
        db.commit()
        db.refresh(log_source)
        
        logger.info(f"Created log source: {log_source.id} for service: {service.name}")
        
        return LogSourceResponse(
            id=log_source.id,
            name=log_source.name,
            service_id=log_source.service_id,
            service_name=service.name,
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
        logger.error(f"Error creating log source: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create log source")

@router.get("/{log_source_id}", response_model=LogSourceResponse)
def get_log_source(log_source_id: str, db: Session = Depends(get_db_dependency)):
    """Get details of a specific log source"""
    try:
        log_source = db.query(LogSource).join(Service).filter(
            LogSource.id == log_source_id,
            LogSource.is_active == True,
            Service.is_active == True
        ).first()
        
        if not log_source:
            raise HTTPException(status_code=404, detail="Log source not found")
        
        # Count active exceptions
        active_exceptions = db.query(ExceptionCluster).filter(
            ExceptionCluster.log_source_id == log_source.id,
            ExceptionCluster.status == 'active'
        ).count()
        
        return LogSourceResponse(
            id=log_source.id,
            name=log_source.name,
            service_id=log_source.service_id,
            service_name=log_source.service.name,
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
            active_exceptions_count=active_exceptions,
            created_at=log_source.created_at,
            updated_at=log_source.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting log source {log_source_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get log source")

@router.put("/{log_source_id}", response_model=LogSourceResponse)
def update_log_source(log_source_id: str, request: LogSourceUpdateRequest, db: Session = Depends(get_db_dependency)):
    """Update log source configuration"""
    try:
        log_source = db.query(LogSource).join(Service).filter(
            LogSource.id == log_source_id,
            LogSource.is_active == True,
            Service.is_active == True
        ).first()
        
        if not log_source:
            raise HTTPException(status_code=404, detail="Log source not found")
        
        # Update fields if provided
        update_data = request.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(log_source, field, value)
        
        log_source.updated_at = datetime.utcnow()
        
        # Reset connection status if connection details changed
        connection_fields = ['host', 'port', 'username', 'password', 'use_ssl', 'verify_certs']
        if any(field in update_data for field in connection_fields):
            log_source.connection_status = 'unknown'
            log_source.last_connection_test = None
        
        db.commit()
        db.refresh(log_source)
        
        # Count active exceptions
        active_exceptions = db.query(ExceptionCluster).filter(
            ExceptionCluster.log_source_id == log_source.id,
            ExceptionCluster.status == 'active'
        ).count()
        
        logger.info(f"Updated log source: {log_source.id}")
        
        return LogSourceResponse(
            id=log_source.id,
            name=log_source.name,
            service_id=log_source.service_id,
            service_name=log_source.service.name,
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
            active_exceptions_count=active_exceptions,
            created_at=log_source.created_at,
            updated_at=log_source.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating log source {log_source_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update log source")

@router.delete("/{log_source_id}")
def delete_log_source(log_source_id: str, db: Session = Depends(get_db_dependency)):
    """Delete a log source (soft delete)"""
    try:
        log_source = db.query(LogSource).filter(
            LogSource.id == log_source_id,
            LogSource.is_active == True
        ).first()
        
        if not log_source:
            raise HTTPException(status_code=404, detail="Log source not found")
        
        # Soft delete
        log_source.is_active = False
        log_source.fetch_enabled = False
        log_source.updated_at = datetime.utcnow()
        
        db.commit()
        
        logger.info(f"Deleted log source: {log_source.id}")
        
        return {"message": "Log source deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting log source {log_source_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete log source")

# ============================================================================
# CONNECTION TESTING
# ============================================================================

@router.post("/{log_source_id}/test", response_model=ConnectionTestResponse)
def test_connection(log_source_id: str, db: Session = Depends(get_db_dependency)):
    """Test connection to a log source"""
    try:
        log_source = db.query(LogSource).filter(
            LogSource.id == log_source_id,
            LogSource.is_active == True
        ).first()
        
        if not log_source:
            raise HTTPException(status_code=404, detail="Log source not found")
        
        start_time = datetime.utcnow()
        
        try:
            # Create connector and test connection
            if log_source.source_type in ['opensearch', 'elasticsearch']:
                connector = OpenSearchConnector(
                    host=log_source.host,
                    port=log_source.port,
                    username=log_source.username,
                    password=log_source.password,
                    use_ssl=log_source.use_ssl,
                    verify_certs=log_source.verify_certs
                )
                
                # Test basic connectivity
                info = connector.client.info()
                
                # Test index access
                indices = connector.client.indices.get_alias(index=log_source.index_pattern)
                
                end_time = datetime.utcnow()
                response_time = int((end_time - start_time).total_seconds() * 1000)
                
                # Update log source status
                log_source.connection_status = 'connected'
                log_source.last_connection_test = datetime.utcnow()
                log_source.last_error = None
                db.commit()
                
                return ConnectionTestResponse(
                    success=True,
                    message="Connection successful",
                    details={
                        "cluster_name": info.get("cluster_name", "Unknown"),
                        "version": info.get("version", {}).get("number", "Unknown"),
                        "indices_found": len(indices)
                    },
                    response_time_ms=response_time
                )
                
            else:
                # For other source types, return not implemented
                return ConnectionTestResponse(
                    success=False,
                    message=f"Connection testing not implemented for {log_source.source_type}",
                    details={"source_type": log_source.source_type}
                )
                
        except Exception as conn_error:
            # Update log source status
            log_source.connection_status = 'error'
            log_source.last_connection_test = datetime.utcnow()
            log_source.last_error = str(conn_error)
            db.commit()
            
            return ConnectionTestResponse(
                success=False,
                message=f"Connection failed: {str(conn_error)}",
                details={"error_type": type(conn_error).__name__}
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing connection for log source {log_source_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to test connection")

# ============================================================================
# MONITORING CONTROL
# ============================================================================

@router.post("/{log_source_id}/monitoring", response_model=MonitoringStatusResponse)
def control_monitoring(log_source_id: str, request: MonitoringControlRequest, db: Session = Depends(get_db_dependency)):
    """Enable or disable monitoring for a log source"""
    try:
        log_source = db.query(LogSource).join(Service).filter(
            LogSource.id == log_source_id,
            LogSource.is_active == True,
            Service.is_active == True
        ).first()
        
        if not log_source:
            raise HTTPException(status_code=404, detail="Log source not found")
        
        if request.apply_to_all:
            # Apply to all log sources in the service
            db.query(LogSource).filter(
                LogSource.service_id == log_source.service_id,
                LogSource.is_active == True
            ).update({
                "fetch_enabled": request.enabled,
                "updated_at": datetime.utcnow()
            })
            
            logger.info(f"Updated monitoring for all log sources in service: {log_source.service_id} to {request.enabled}")
        else:
            # Apply to specific log source
            log_source.fetch_enabled = request.enabled
            log_source.updated_at = datetime.utcnow()
            
            logger.info(f"Updated monitoring for log source: {log_source.id} to {request.enabled}")
        
        db.commit()
        db.refresh(log_source)
        
        # Calculate next fetch time
        next_fetch_at = None
        if log_source.fetch_enabled and log_source.last_fetch_at:
            from datetime import timedelta
            next_fetch_at = log_source.last_fetch_at + timedelta(minutes=log_source.fetch_interval_minutes)
        
        return MonitoringStatusResponse(
            log_source_id=log_source.id,
            log_source_name=log_source.name,
            service_id=log_source.service_id,
            service_name=log_source.service.name,
            monitoring_enabled=log_source.is_active,
            fetch_enabled=log_source.fetch_enabled,
            connection_status=log_source.connection_status,
            last_fetch_at=log_source.last_fetch_at,
            next_fetch_at=next_fetch_at,
            fetch_interval_minutes=log_source.fetch_interval_minutes
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error controlling monitoring for log source {log_source_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to control monitoring")

@router.get("/monitoring/status", response_model=List[MonitoringStatusResponse])
def get_monitoring_status(db: Session = Depends(get_db_dependency)):
    """Get monitoring status for all log sources"""
    try:
        log_sources = db.query(LogSource).join(Service).filter(
            LogSource.is_active == True,
            Service.is_active == True
        ).all()
        
        result = []
        for log_source in log_sources:
            # Calculate next fetch time
            next_fetch_at = None
            if log_source.fetch_enabled and log_source.last_fetch_at:
                from datetime import timedelta
                next_fetch_at = log_source.last_fetch_at + timedelta(minutes=log_source.fetch_interval_minutes)
            
            result.append(MonitoringStatusResponse(
                log_source_id=log_source.id,
                log_source_name=log_source.name,
                service_id=log_source.service_id,
                service_name=log_source.service.name,
                monitoring_enabled=log_source.is_active,
                fetch_enabled=log_source.fetch_enabled,
                connection_status=log_source.connection_status,
                last_fetch_at=log_source.last_fetch_at,
                next_fetch_at=next_fetch_at,
                fetch_interval_minutes=log_source.fetch_interval_minutes
            ))
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting monitoring status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get monitoring status")

# ============================================================================
# BULK OPERATIONS
# ============================================================================

@router.post("/monitoring/enable-all")
def enable_all_monitoring(service_id: Optional[str] = None, db: Session = Depends(get_db_dependency)):
    """Enable monitoring for all log sources (optionally filtered by service)"""
    try:
        query = db.query(LogSource).filter(LogSource.is_active == True)
        
        if service_id:
            # Verify service exists
            service = db.query(Service).filter(
                Service.id == service_id,
                Service.is_active == True
            ).first()
            
            if not service:
                raise HTTPException(status_code=404, detail="Service not found")
            
            query = query.filter(LogSource.service_id == service_id)
        
        updated_count = query.update({
            "fetch_enabled": True,
            "updated_at": datetime.utcnow()
        })
        
        db.commit()
        
        logger.info(f"Enabled monitoring for {updated_count} log sources" + 
                   (f" in service {service_id}" if service_id else ""))
        
        return {"message": f"Enabled monitoring for {updated_count} log sources"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enabling all monitoring: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to enable monitoring")

@router.post("/monitoring/disable-all")
def disable_all_monitoring(service_id: Optional[str] = None, db: Session = Depends(get_db_dependency)):
    """Disable monitoring for all log sources (optionally filtered by service)"""
    try:
        query = db.query(LogSource).filter(LogSource.is_active == True)
        
        if service_id:
            # Verify service exists
            service = db.query(Service).filter(
                Service.id == service_id,
                Service.is_active == True
            ).first()
            
            if not service:
                raise HTTPException(status_code=404, detail="Service not found")
            
            query = query.filter(LogSource.service_id == service_id)
        
        updated_count = query.update({
            "fetch_enabled": False,
            "updated_at": datetime.utcnow()
        })
        
        db.commit()
        
        logger.info(f"Disabled monitoring for {updated_count} log sources" + 
                   (f" in service {service_id}" if service_id else ""))
        
        return {"message": f"Disabled monitoring for {updated_count} log sources"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disabling all monitoring: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to disable monitoring")
