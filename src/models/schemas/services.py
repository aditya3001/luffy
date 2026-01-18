"""
Service and Log Source Pydantic schemas.
Handles validation and serialization for service management APIs.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import Field, field_validator
from enum import Enum

from .base import BaseSchema, TimestampMixin, PaginatedResponse


class LogSourceTypeEnum(str, Enum):
    """Supported log source types."""
    
    OPENSEARCH = "opensearch"
    ELASTICSEARCH = "elasticsearch"
    LOKI = "loki"
    CLOUDWATCH = "cloudwatch"
    SPLUNK = "splunk"
    FLUENTD = "fluentd"
    SYSLOG = "syslog"


class ConnectionStatusEnum(str, Enum):
    """Log source connection status."""
    
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    UNKNOWN = "unknown"
    TESTING = "testing"


# Service Schemas

class ServiceCreateRequest(BaseSchema):
    """Schema for creating a new service."""
    
    name: str = Field(..., min_length=1, max_length=100, description="Service name")
    description: Optional[str] = Field(None, max_length=500, description="Service description")
    version: Optional[str] = Field(None, max_length=50, description="Service version")
    repository_url: Optional[str] = Field(None, description="Repository URL")
    commit_sha: Optional[str] = Field(None, max_length=40, description="Current commit SHA")
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """Validate service name format."""
        if not v.replace('-', '').replace('_', '').replace('.', '').isalnum():
            raise ValueError("Service name can only contain alphanumeric characters, hyphens, underscores, and dots")
        return v.lower()


class ServiceUpdateRequest(BaseSchema):
    """Schema for updating a service."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Service name")
    description: Optional[str] = Field(None, max_length=500, description="Service description")
    version: Optional[str] = Field(None, max_length=50, description="Service version")
    repository_url: Optional[str] = Field(None, description="Repository URL")
    commit_sha: Optional[str] = Field(None, max_length=40, description="Current commit SHA")
    is_active: Optional[bool] = Field(None, description="Whether service is active")


class ServiceResponse(BaseSchema, TimestampMixin):
    """Schema for service response."""
    
    id: str = Field(..., description="Service ID")
    name: str = Field(..., description="Service name")
    description: Optional[str] = Field(None, description="Service description")
    version: Optional[str] = Field(None, description="Service version")
    repository_url: Optional[str] = Field(None, description="Repository URL")
    commit_sha: Optional[str] = Field(None, description="Current commit SHA")
    is_active: bool = Field(..., description="Whether service is active")
    
    # Computed fields
    total_log_sources: int = Field(0, description="Number of log sources")
    active_log_sources: int = Field(0, description="Number of active log sources")
    total_clusters: int = Field(0, description="Total exception clusters")


class ServiceListResponse(PaginatedResponse):
    """Paginated service list response."""
    
    items: List[ServiceResponse] = Field(..., description="List of services")


# Log Source Schemas

class LogSourceCreateRequest(BaseSchema):
    """Schema for creating a new log source."""
    
    service_id: str = Field(..., description="Service ID")
    name: str = Field(..., min_length=1, max_length=100, description="Log source name")
    source_type: LogSourceTypeEnum = Field(..., description="Log source type")
    
    # Connection configuration
    host: str = Field(..., min_length=1, description="Host address")
    port: int = Field(9200, ge=1, le=65535, description="Port number")
    username: Optional[str] = Field(None, description="Username for authentication")
    password: Optional[str] = Field(None, description="Password for authentication")
    use_ssl: bool = Field(True, description="Use SSL/TLS")
    verify_certs: bool = Field(True, description="Verify SSL certificates")
    
    # Index/query configuration
    index_pattern: str = Field(..., min_length=1, description="Index pattern")
    query_filter: Optional[Dict[str, Any]] = Field(None, description="Additional query filters")
    
    # Task configuration
    fetch_enabled: bool = Field(True, description="Enable log fetching")
    fetch_interval_minutes: int = Field(30, ge=1, le=1440, description="Fetch interval in minutes")
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """Validate log source name format."""
        if not v.replace('-', '').replace('_', '').replace(' ', '').isalnum():
            raise ValueError("Log source name can only contain alphanumeric characters, hyphens, underscores, and spaces")
        return v
    
    @field_validator('index_pattern')
    @classmethod
    def validate_index_pattern(cls, v):
        """Validate index pattern format."""
        if not v:
            raise ValueError("Index pattern cannot be empty")
        # Basic validation - could be more sophisticated
        if len(v) > 200:
            raise ValueError("Index pattern too long")
        return v


class LogSourceUpdateRequest(BaseSchema):
    """Schema for updating a log source."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Log source name")
    
    # Connection configuration
    host: Optional[str] = Field(None, min_length=1, description="Host address")
    port: Optional[int] = Field(None, ge=1, le=65535, description="Port number")
    username: Optional[str] = Field(None, description="Username for authentication")
    password: Optional[str] = Field(None, description="Password for authentication")
    use_ssl: Optional[bool] = Field(None, description="Use SSL/TLS")
    verify_certs: Optional[bool] = Field(None, description="Verify SSL certificates")
    
    # Index/query configuration
    index_pattern: Optional[str] = Field(None, min_length=1, description="Index pattern")
    query_filter: Optional[Dict[str, Any]] = Field(None, description="Additional query filters")
    
    # Task configuration
    is_active: Optional[bool] = Field(None, description="Whether log source is active")
    fetch_enabled: Optional[bool] = Field(None, description="Enable log fetching")
    fetch_interval_minutes: Optional[int] = Field(None, ge=1, le=1440, description="Fetch interval in minutes")


class LogSourceResponse(BaseSchema, TimestampMixin):
    """Schema for log source response."""
    
    id: str = Field(..., description="Log source ID")
    service_id: str = Field(..., description="Service ID")
    name: str = Field(..., description="Log source name")
    source_type: LogSourceTypeEnum = Field(..., description="Log source type")
    
    # Connection configuration
    host: str = Field(..., description="Host address")
    port: int = Field(..., description="Port number")
    username: Optional[str] = Field(None, description="Username for authentication")
    # Note: password is never returned in responses
    use_ssl: bool = Field(..., description="Use SSL/TLS")
    verify_certs: bool = Field(..., description="Verify SSL certificates")
    
    # Index/query configuration
    index_pattern: str = Field(..., description="Index pattern")
    query_filter: Optional[Dict[str, Any]] = Field(None, description="Additional query filters")
    
    # Task configuration
    is_active: bool = Field(..., description="Whether log source is active")
    fetch_enabled: bool = Field(..., description="Enable log fetching")
    fetch_interval_minutes: int = Field(..., description="Fetch interval in minutes")
    
    # Status
    connection_status: ConnectionStatusEnum = Field(..., description="Connection status")
    last_connection_test: Optional[datetime] = Field(None, description="Last connection test time")
    last_fetch_at: Optional[datetime] = Field(None, description="Last successful fetch time")
    last_error: Optional[str] = Field(None, description="Last error message")
    
    # Computed fields
    total_clusters: int = Field(0, description="Total exception clusters from this source")
    
    # Computed properties
    @property
    def connection_url(self) -> str:
        """Get connection URL (without credentials)."""
        protocol = "https" if self.use_ssl else "http"
        return f"{protocol}://{self.host}:{self.port}"


class LogSourceListResponse(PaginatedResponse):
    """Paginated log source list response."""
    
    items: List[LogSourceResponse] = Field(..., description="List of log sources")


class LogSourceTestRequest(BaseSchema):
    """Schema for testing log source connection."""
    
    # Optional override parameters for testing
    host: Optional[str] = Field(None, description="Override host for testing")
    port: Optional[int] = Field(None, ge=1, le=65535, description="Override port for testing")
    username: Optional[str] = Field(None, description="Override username for testing")
    password: Optional[str] = Field(None, description="Override password for testing")
    use_ssl: Optional[bool] = Field(None, description="Override SSL setting for testing")
    verify_certs: Optional[bool] = Field(None, description="Override cert verification for testing")
    index_pattern: Optional[str] = Field(None, description="Override index pattern for testing")


class LogSourceTestResponse(BaseSchema):
    """Schema for log source connection test result."""
    
    success: bool = Field(..., description="Whether the test was successful")
    status: ConnectionStatusEnum = Field(..., description="Connection status")
    message: str = Field(..., description="Test result message")
    response_time_ms: Optional[float] = Field(None, description="Response time in milliseconds")
    
    # Test details
    details: Optional[Dict[str, Any]] = Field(None, description="Additional test details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Test timestamp")


# Filter and Search Schemas

class ServiceFilterParams(BaseSchema):
    """Service filtering parameters."""
    
    search: Optional[str] = Field(None, description="Search in name and description")
    is_active: Optional[bool] = Field(None, description="Filter by active status")
    has_log_sources: Optional[bool] = Field(None, description="Filter services with/without log sources")


class LogSourceFilterParams(BaseSchema):
    """Log source filtering parameters."""
    
    search: Optional[str] = Field(None, description="Search in name")
    service_id: Optional[str] = Field(None, description="Filter by service ID")
    source_type: Optional[LogSourceTypeEnum] = Field(None, description="Filter by source type")
    is_active: Optional[bool] = Field(None, description="Filter by active status")
    connection_status: Optional[ConnectionStatusEnum] = Field(None, description="Filter by connection status")
    fetch_enabled: Optional[bool] = Field(None, description="Filter by fetch enabled status")


# Bulk Operations

class ServiceBulkUpdateRequest(BaseSchema):
    """Bulk service update request."""
    
    service_ids: List[str] = Field(..., min_items=1, max_items=50, description="Service IDs to update")
    updates: ServiceUpdateRequest = Field(..., description="Updates to apply")


class LogSourceBulkUpdateRequest(BaseSchema):
    """Bulk log source update request."""
    
    log_source_ids: List[str] = Field(..., min_items=1, max_items=50, description="Log source IDs to update")
    updates: LogSourceUpdateRequest = Field(..., description="Updates to apply")


# Statistics and Metrics

class ServiceStatsResponse(BaseSchema):
    """Service statistics response."""
    
    total_services: int = Field(..., description="Total number of services")
    active_services: int = Field(..., description="Number of active services")
    total_log_sources: int = Field(..., description="Total number of log sources")
    active_log_sources: int = Field(..., description="Number of active log sources")
    
    # By source type
    log_sources_by_type: Dict[str, int] = Field(..., description="Log sources count by type")
    
    # Connection status
    connected_sources: int = Field(..., description="Number of connected log sources")
    disconnected_sources: int = Field(..., description="Number of disconnected log sources")
    error_sources: int = Field(..., description="Number of log sources with errors")


class LogSourceStatsResponse(BaseSchema):
    """Log source statistics response."""
    
    service_id: str = Field(..., description="Service ID")
    total_log_sources: int = Field(..., description="Total log sources for this service")
    active_log_sources: int = Field(..., description="Active log sources for this service")
    
    # Status breakdown
    status_breakdown: Dict[ConnectionStatusEnum, int] = Field(..., description="Count by connection status")
    
    # Type breakdown
    type_breakdown: Dict[LogSourceTypeEnum, int] = Field(..., description="Count by source type")
    
    # Recent activity
    recent_errors: List[str] = Field(..., description="Recent error messages")
    last_successful_fetch: Optional[datetime] = Field(None, description="Last successful fetch across all sources")
