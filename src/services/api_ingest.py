"""
Fluent Bit Log Ingestion API

This module provides REST API endpoints for real-time log ingestion from Fluent Bit.
Supports batch ingestion, authentication, rate limiting, and async processing.
"""
import logging
import hashlib
import time
import uuid

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Header, Request, BackgroundTasks, Depends, Body
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from src.config import settings
from src.storage.database import get_db_dependency
from src.storage.models import LogSource, Service
from src.services.tasks import process_log_batch

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/api/v1/ingest", tags=["ingestion"])

# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class LogEntry(BaseModel):
    """Single log entry from Fluent Bit"""
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    level: str = Field(..., description="Log level (ERROR, FATAL, etc.)")
    logger: str = Field(..., description="Logger name")
    message: str = Field(..., description="Log message")
    exception_type: Optional[str] = Field(None, description="Exception class name")
    exception_message: Optional[str] = Field(None, description="Exception message")
    stack_trace: Optional[str] = Field(None, description="Full stack trace")
    service_id: str = Field(..., description="Service identifier")
    service_name: Optional[str] = Field(None, description="Service display name")
    environment: Optional[str] = Field(None, description="Environment (prod, staging, dev)")
    hostname: Optional[str] = Field(None, description="Host/pod name")
    file_path: Optional[str] = Field(None, description="Source file path")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    
    @field_validator('level')
    @classmethod
    def validate_level(cls, v: str) -> str:
        """Normalize log level to uppercase"""
        return v.upper()
    
    @field_validator('message')
    @classmethod
    def validate_message(cls, v: str) -> str:
        """Ensure message is not empty and within size limit"""
        if not v or not v.strip():
            raise ValueError("Message cannot be empty")
        if len(v) > 50000:  # 50KB limit
            logger.warning(f"Message truncated from {len(v)} to 50000 characters")
            return v[:50000]
        return v
    
    @field_validator('stack_trace')
    @classmethod
    def validate_stack_trace(cls, v: Optional[str]) -> Optional[str]:
        """Ensure stack trace is within size limit"""
        if v and len(v) > 100000:  # 100KB limit
            logger.warning(f"Stack trace truncated from {len(v)} to 100000 characters")
            return v[:100000]
        return v


class IngestLogsRequest(BaseModel):
    """Batch log ingestion request"""
    logs: List[LogEntry] = Field(..., description="List of log entries", min_length=1, max_length=1000)
    
    @field_validator('logs')
    @classmethod
    def validate_batch_size(cls, v: List[LogEntry]) -> List[LogEntry]:
        """Validate batch size"""
        if len(v) > 1000:
            raise ValueError("Batch size cannot exceed 1000 logs")
        return v


class IngestLogsResponse(BaseModel):
    """Batch log ingestion response"""
    status: str = Field(..., description="Status (accepted, rejected)")
    received_count: int = Field(..., description="Number of logs received")
    accepted_count: int = Field(..., description="Number of logs accepted")
    rejected_count: int = Field(..., description="Number of logs rejected")
    task_id: Optional[str] = Field(None, description="Celery task ID")
    message: str = Field(..., description="Response message")
    errors: Optional[List[str]] = Field(default_factory=list, description="Error messages")


class IngestionMetrics(BaseModel):
    """Ingestion metrics"""
    total_logs_received: int
    total_logs_accepted: int
    total_logs_rejected: int
    logs_per_second: float
    avg_batch_size: float
    avg_processing_time_ms: float
    services_active: int
    last_ingestion: Optional[datetime]


class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: datetime
    version: str
    uptime_seconds: float
    rate_limit_remaining: int
    queue_depth: int


# ============================================================================
# AUTHENTICATION & AUTHORIZATION
# ============================================================================

def verify_api_token(authorization: str = Header(None)) -> str:
    """
    Verify API token from Authorization header.
    
    Args:
        authorization: Authorization header value (Bearer <token>)
        
    Returns:
        Token value
        
    Raises:
        HTTPException: If token is missing or invalid
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header"
        )
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header format. Expected: Bearer <token>"
        )
    
    token = authorization.replace("Bearer ", "")
    
    # Validate token (in production, use proper JWT validation)
    # For now, check against configured token
    if token != settings.fluent_bit_api_token:
        raise HTTPException(
            status_code=401,
            detail="Invalid API token"
        )
    
    return token


def verify_service_access(service_id: str, db: Session) -> Service:
    """
    Verify that service exists and is active.
    
    Args:
        service_id: Service identifier
        db: Database session
        
    Returns:
        Service object
        
    Raises:
        HTTPException: If service not found or inactive
    """
    service = db.query(Service).filter(Service.id == service_id).first()
    
    if not service:
        raise HTTPException(
            status_code=404,
            detail=f"Service not found: {service_id}"
        )
    
    if not service.is_active:
        raise HTTPException(
            status_code=403,
            detail=f"Service is inactive: {service_id}"
        )
    
    return service


# ============================================================================
# RATE LIMITING
# ============================================================================

class RateLimiter:
    """
    Simple in-memory rate limiter.
    In production, use Redis-based rate limiting.
    """
    def __init__(self):
        self.requests: Dict[str, List[float]] = {}
        self.window_seconds = 60
        self.max_requests_per_window = 10000  # 10K logs per minute per service
    
    def check_rate_limit(self, service_id: str, log_count: int) -> tuple[bool, int]:
        """
        Check if service is within rate limit.
        
        Args:
            service_id: Service identifier
            log_count: Number of logs in current request
            
        Returns:
            Tuple of (allowed, remaining)
        """
        now = time.time()
        
        # Initialize service if not exists
        if service_id not in self.requests:
            self.requests[service_id] = []
        
        # Remove old requests outside window
        self.requests[service_id] = [
            req_time for req_time in self.requests[service_id]
            if now - req_time < self.window_seconds
        ]
        
        # Count current requests in window
        current_count = len(self.requests[service_id])
        
        # Check if adding new logs would exceed limit
        if current_count + log_count > self.max_requests_per_window:
            remaining = max(0, self.max_requests_per_window - current_count)
            return False, remaining
        
        # Add current request
        for _ in range(log_count):
            self.requests[service_id].append(now)
        
        remaining = self.max_requests_per_window - (current_count + log_count)
        return True, remaining


# Global rate limiter instance
rate_limiter = RateLimiter()


# ============================================================================
# DEDUPLICATION
# ============================================================================

def generate_log_hash(log: LogEntry) -> str:
    """
    Generate unique hash for log entry to detect duplicates.
    
    Args:
        log: Log entry
        
    Returns:
        SHA256 hash
    """
    # Create hash from key fields
    hash_input = f"{log.timestamp}|{log.service_id}|{log.logger}|{log.message}"
    if log.exception_type:
        hash_input += f"|{log.exception_type}"
    if log.stack_trace:
        # Use first 1000 chars of stack trace to avoid huge hashes
        hash_input += f"|{log.stack_trace[:1000]}"
    
    return hashlib.sha256(hash_input.encode()).hexdigest()


# In-memory deduplication cache (last 10 minutes)
# In production, use Redis with TTL
dedup_cache: Dict[str, float] = {}
DEDUP_WINDOW_SECONDS = 600  # 10 minutes


def is_duplicate(log: LogEntry) -> bool:
    """
    Check if log is a duplicate within deduplication window.
    
    Args:
        log: Log entry
        
    Returns:
        True if duplicate, False otherwise
    """
    now = time.time()
    log_hash = generate_log_hash(log)
    
    # Clean old entries
    global dedup_cache
    dedup_cache = {
        h: t for h, t in dedup_cache.items()
        if now - t < DEDUP_WINDOW_SECONDS
    }
    
    # Check if hash exists
    if log_hash in dedup_cache:
        return True
    
    # Add to cache
    dedup_cache[log_hash] = now
    return False


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.post("/logs", response_model=IngestLogsResponse)
async def ingest_logs(
    raw_logs: List[LogEntry] = Body(...),
    authorization: str = Header(None),
    db: Session = Depends(get_db_dependency)
):
    """
    Ingest logs from Fluent Bit (array payload)
    """

    # Wrap Fluent Bit payload into your domain model
    request = IngestLogsRequest(logs=raw_logs)
    """
    Ingest a batch of error logs from Fluent Bit.
    
    This endpoint:
    1. Validates authentication (API token)
    2. Validates service access
    3. Checks rate limits
    4. Deduplicates logs
    5. Queues logs for async processing
    6. Returns immediate acknowledgment
    
    Args:
        request: Batch of log entries
        background_tasks: FastAPI background tasks
        authorization: Authorization header (Bearer token)
        db: Database session
        
    Returns:
        Ingestion response with task ID
    """
    start_time = time.time()
    
    try:
        # 1. Verify API token
        verify_api_token(authorization)
        
        # 2. Get database session
        if db is None:
            db = next(get_db_dependency())
        
        # 3. Validate service access (use first log's service_id)
        service_id = request.logs[0].service_id
        service = verify_service_access(service_id, db)
        
        # 3.5. Check if log processing is enabled for this service
        if not service.log_processing_enabled:
            logger.warning(f"Log processing disabled for service {service.name}, rejecting logs")
            return IngestLogsResponse(
                status="rejected",
                received_count=len(request.logs),
                accepted_count=0,
                rejected_count=len(request.logs),
                message=f"Log processing is disabled for service '{service.name}'. Enable it in the dashboard to process logs.",
                errors=[f"Service '{service.name}' has log processing disabled"]
            )
        
        # 4. Check rate limit
        allowed, remaining = rate_limiter.check_rate_limit(service_id, len(request.logs))
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Try again later. Remaining: {remaining}"
            )
        
        # 5. Deduplicate logs
        unique_logs = []
        duplicate_count = 0
        for log in request.logs:
            if not is_duplicate(log):
                unique_logs.append(log.model_dump())
            else:
                duplicate_count += 1
        
        if duplicate_count > 0:
            logger.info(f"Filtered {duplicate_count} duplicate logs for service {service_id}")
        
        # 6. Queue logs for async processing
        if unique_logs:
            # Get or create default log source for service
            log_source = db.query(LogSource).filter(
                LogSource.service_id == service_id,
                LogSource.source_type == 'fluent-bit'
            ).first()
            
            if not log_source:
                # Create default Fluent Bit log source
                log_source = LogSource(
                    id=str(uuid.uuid4()),
                    name=f"{service.name} - Fluent Bit",
                    service_id=service_id,
                    source_type='fluent-bit',
                    host='fluent-bit',
                    port=2020,
                    index_pattern='fluent-bit-*',
                    fetch_enabled=True,
                    connection_status='connected'
                )
                db.add(log_source)
                db.commit()
                db.refresh(log_source)
            
            # Queue for processing
            task = process_log_batch.delay(unique_logs, log_source.id)
            task_id = task.id
            
            logger.info(
                f"Queued {len(unique_logs)} logs for service {service_id} "
                f"(task: {task_id}, duplicates: {duplicate_count})"
            )
        else:
            task_id = None
            logger.info(f"All {len(request.logs)} logs were duplicates for service {service_id}")
        
        # 7. Return response
        processing_time_ms = (time.time() - start_time) * 1000
        
        return IngestLogsResponse(
            status="accepted",
            received_count=len(request.logs),
            accepted_count=len(unique_logs),
            rejected_count=duplicate_count,
            task_id=task_id,
            message=f"Logs queued for processing (processing time: {processing_time_ms:.2f}ms)",
            errors=[]
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ingesting logs: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.post("/logs/single", response_model=IngestLogsResponse)
async def ingest_single_log(
    log: LogEntry,
    background_tasks: BackgroundTasks,
    authorization: str = Header(None),
    db: Session = Depends(get_db_dependency)
):
    """
    Ingest a single log entry (for testing).
    
    Args:
        log: Single log entry
        background_tasks: FastAPI background tasks
        authorization: Authorization header
        db: Database session
        
    Returns:
        Ingestion response
    """
    # Convert single log to batch request
    request = IngestLogsRequest(logs=[log])
    return await ingest_logs(request, background_tasks, authorization, db)


@router.get("/metrics", response_model=IngestionMetrics)
async def get_ingestion_metrics(
    authorization: str = Header(None)
):
    """
    Get ingestion metrics.
    
    Args:
        authorization: Authorization header
        db: Database session
        
    Returns:
        Ingestion metrics
    """
    verify_api_token(authorization)
    
    # TODO: Implement metrics tracking in Redis/database
    # For now, return placeholder metrics
    return IngestionMetrics(
        total_logs_received=0,
        total_logs_accepted=0,
        total_logs_rejected=0,
        logs_per_second=0.0,
        avg_batch_size=0.0,
        avg_processing_time_ms=0.0,
        services_active=0,
        last_ingestion=None
    )


@router.get("/health", response_model=HealthCheckResponse)
async def health_check(
    authorization: str = Header(None)
):
    """
    Health check endpoint for Fluent Bit monitoring.
    
    Args:
        authorization: Authorization header
        
    Returns:
        Health status
    """
    verify_api_token(authorization)
    
    # TODO: Implement proper health checks
    # - Check database connection
    # - Check Redis connection
    # - Check Celery workers
    # - Check queue depth
    
    return HealthCheckResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        version="1.0.0",
        uptime_seconds=0.0,
        rate_limit_remaining=10000,
        queue_depth=0
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    'router',
    'LogEntry',
    'IngestLogsRequest',
    'IngestLogsResponse',
    'IngestionMetrics',
    'HealthCheckResponse'
]
