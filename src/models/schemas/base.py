"""
Base Pydantic schemas for API validation and serialization.
Provides common schemas and utilities for all API endpoints.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator, ConfigDict
from enum import Enum


class BaseSchema(BaseModel):
    """Base schema with common configuration."""
    
    model_config = ConfigDict(
        # Allow ORM models to be converted to Pydantic models
        from_attributes=True,
        # Use enum values instead of names
        use_enum_values=True,
        # Validate assignment
        validate_assignment=True,
        # Allow population by field name or alias
        populate_by_name=True
    )


class TimestampMixin:
    """Mixin for schemas with timestamp fields."""
    
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class PaginationParams(BaseSchema):
    """Pagination parameters for list endpoints."""
    
    page: int = Field(1, ge=1, description="Page number (1-based)")
    size: int = Field(20, ge=1, le=100, description="Page size (max 100)")
    
    @property
    def offset(self) -> int:
        """Calculate offset for database queries."""
        return (self.page - 1) * self.size


class PaginatedResponse(BaseSchema):
    """Generic paginated response wrapper."""
    
    items: List[Any] = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Page size")
    pages: int = Field(..., description="Total number of pages")
    
    @field_validator('pages')
    @classmethod
    def calculate_pages(cls, v, info):
        """Calculate total pages based on total and size."""
        if info.data:
            total = info.data.get('total', 0)
            size = info.data.get('size', 20)
            return (total + size - 1) // size if size > 0 else 0
        return v


class SortParams(BaseSchema):
    """Sorting parameters for list endpoints."""
    
    sort_by: Optional[str] = Field(None, description="Field to sort by")
    sort_order: Optional[str] = Field("asc", pattern="^(asc|desc)$", description="Sort order")


class FilterParams(BaseSchema):
    """Base filtering parameters."""
    
    search: Optional[str] = Field(None, description="Search query")
    date_from: Optional[datetime] = Field(None, description="Filter from date")
    date_to: Optional[datetime] = Field(None, description="Filter to date")


class StatusEnum(str, Enum):
    """Common status enumeration."""
    
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SeverityEnum(str, Enum):
    """Exception severity enumeration."""
    
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ResponseStatus(str, Enum):
    """API response status enumeration."""
    
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"


class APIResponse(BaseSchema):
    """Standard API response wrapper."""
    
    status: ResponseStatus = Field(..., description="Response status")
    message: str = Field(..., description="Response message")
    data: Optional[Any] = Field(None, description="Response data")
    errors: Optional[List[str]] = Field(None, description="List of errors")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


class SuccessResponse(APIResponse):
    """Success response wrapper."""
    
    status: ResponseStatus = ResponseStatus.SUCCESS


class ErrorResponse(APIResponse):
    """Error response wrapper."""
    
    status: ResponseStatus = ResponseStatus.ERROR
    data: Optional[Any] = None


class ValidationErrorDetail(BaseSchema):
    """Validation error detail."""
    
    field: str = Field(..., description="Field name with error")
    message: str = Field(..., description="Error message")
    value: Optional[Any] = Field(None, description="Invalid value")


class ValidationErrorResponse(ErrorResponse):
    """Validation error response."""
    
    errors: List[ValidationErrorDetail] = Field(..., description="Validation errors")


class HealthCheckResponse(BaseSchema):
    """Health check response schema."""
    
    status: str = Field(..., description="Health status")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str = Field(..., description="Application version")
    uptime_seconds: float = Field(..., description="Uptime in seconds")
    
    # Component health
    database: bool = Field(..., description="Database connectivity")
    redis: bool = Field(..., description="Redis connectivity")
    celery: bool = Field(..., description="Celery worker status")
    
    # Optional details
    details: Optional[Dict[str, Any]] = Field(None, description="Additional health details")


class MetricsResponse(BaseSchema):
    """Metrics response schema."""
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metrics: Dict[str, Any] = Field(..., description="Metrics data")
    
    # Common metrics
    requests_total: Optional[int] = Field(None, description="Total requests")
    requests_per_second: Optional[float] = Field(None, description="Requests per second")
    response_time_avg: Optional[float] = Field(None, description="Average response time")
    error_rate: Optional[float] = Field(None, description="Error rate percentage")


class BulkOperationRequest(BaseSchema):
    """Bulk operation request schema."""
    
    ids: List[str] = Field(..., min_items=1, max_items=100, description="List of IDs to operate on")
    operation: str = Field(..., description="Operation to perform")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Operation parameters")


class BulkOperationResponse(BaseSchema):
    """Bulk operation response schema."""
    
    total: int = Field(..., description="Total items processed")
    successful: int = Field(..., description="Successfully processed items")
    failed: int = Field(..., description="Failed items")
    errors: Optional[List[Dict[str, str]]] = Field(None, description="Errors for failed items")
    
    @field_validator('successful', 'failed')
    @classmethod
    def validate_counts(cls, v, info):
        """Validate that successful + failed = total."""
        if info.data and 'total' in info.data:
            total = info.data['total']
            successful = info.data.get('successful', 0)
            failed = info.data.get('failed', 0)
            if info.field_name == 'failed' and successful + v != total:
                raise ValueError("successful + failed must equal total")
            elif info.field_name == 'successful' and v + info.data.get('failed', 0) != total:
                raise ValueError("successful + failed must equal total")
        return v


class ConfigurationSchema(BaseSchema):
    """Base configuration schema."""
    
    enabled: bool = Field(True, description="Whether the configuration is enabled")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Configuration parameters")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class AuditLogSchema(BaseSchema):
    """Audit log schema."""
    
    id: str = Field(..., description="Audit log ID")
    action: str = Field(..., description="Action performed")
    resource_type: str = Field(..., description="Type of resource")
    resource_id: str = Field(..., description="Resource ID")
    user_id: Optional[str] = Field(None, description="User who performed the action")
    timestamp: datetime = Field(..., description="When the action was performed")
    changes: Optional[Dict[str, Any]] = Field(None, description="Changes made")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
