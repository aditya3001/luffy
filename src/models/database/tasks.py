"""
Task management database models.
Handles task configurations, execution history, and monitoring.
"""
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Column, String, Integer, Float, Boolean, Text, JSON, DateTime
from sqlalchemy.orm import relationship

from .base import BaseModel, UUIDMixin, TimestampMixin


class TaskConfiguration(BaseModel, UUIDMixin, TimestampMixin):
    """
    Task configuration model.
    Stores configuration for background tasks.
    """
    __tablename__ = 'task_configurations'
    
    # Primary key
    id = Column(String, primary_key=True, default=lambda: TaskConfiguration.generate_id())
    
    # Task identification
    task_name = Column(String, nullable=False, unique=True, index=True)
    task_type = Column(String, nullable=False, index=True)  # periodic, manual, triggered
    
    # Configuration
    is_enabled = Column(Boolean, default=True, nullable=False, index=True)
    interval_minutes = Column(Integer)  # For periodic tasks
    cron_expression = Column(String)  # Alternative to interval_minutes
    
    # Task parameters
    parameters = Column(JSON)  # Task-specific parameters
    
    # Metadata
    description = Column(Text)
    priority = Column(Integer, default=0)  # Higher number = higher priority
    timeout_seconds = Column(Integer, default=3600)  # 1 hour default
    max_retries = Column(Integer, default=3)
    
    # Status tracking
    last_run_at = Column(DateTime, index=True)
    next_run_at = Column(DateTime, index=True)
    last_status = Column(String, index=True)  # success, failed, running, skipped
    last_error = Column(Text)
    
    # Audit
    modified_by = Column(String)
    
    # Relationships
    executions = relationship(
        "TaskExecution", 
        back_populates="configuration",
        cascade="all, delete-orphan",
        order_by="TaskExecution.started_at.desc()"
    )
    
    def __repr__(self) -> str:
        return f"<TaskConfiguration(name='{self.task_name}', enabled={self.is_enabled}, status='{self.last_status}')>"
    
    @property
    def is_periodic(self) -> bool:
        """Check if this is a periodic task."""
        return self.task_type == 'periodic'
    
    @property
    def is_manual(self) -> bool:
        """Check if this is a manual task."""
        return self.task_type == 'manual'
    
    @property
    def schedule_description(self) -> str:
        """Get human-readable schedule description."""
        if self.interval_minutes:
            if self.interval_minutes < 60:
                return f"Every {self.interval_minutes} minutes"
            elif self.interval_minutes < 1440:
                hours = self.interval_minutes / 60
                return f"Every {hours:.1f} hours"
            else:
                days = self.interval_minutes / 1440
                return f"Every {days:.1f} days"
        elif self.cron_expression:
            return f"Cron: {self.cron_expression}"
        else:
            return "Manual execution"
    
    @property
    def recent_executions(self) -> list:
        """Get recent executions (last 10)."""
        return self.executions[:10] if self.executions else []
    
    @property
    def success_rate(self) -> Optional[float]:
        """Calculate success rate from recent executions."""
        if not self.executions:
            return None
        
        recent = self.executions[:20]  # Last 20 executions
        successful = sum(1 for ex in recent if ex.status == 'success')
        return successful / len(recent)
    
    def enable(self, modified_by: str) -> None:
        """Enable the task."""
        self.is_enabled = True
        self.modified_by = modified_by
    
    def disable(self, modified_by: str) -> None:
        """Disable the task."""
        self.is_enabled = False
        self.modified_by = modified_by
    
    def update_schedule(self, interval_minutes: Optional[int] = None, 
                       cron_expression: Optional[str] = None,
                       modified_by: str = None) -> None:
        """Update task schedule."""
        if interval_minutes is not None:
            self.interval_minutes = interval_minutes
            self.cron_expression = None
        elif cron_expression is not None:
            self.cron_expression = cron_expression
            self.interval_minutes = None
        
        if modified_by:
            self.modified_by = modified_by
    
    def update_last_run(self, status: str, error: Optional[str] = None) -> None:
        """Update last run information."""
        self.last_run_at = datetime.utcnow()
        self.last_status = status
        self.last_error = error
    
    def calculate_next_run(self) -> Optional[datetime]:
        """Calculate next run time based on schedule."""
        if not self.is_enabled or not self.interval_minutes:
            return None
        
        if self.last_run_at:
            from datetime import timedelta
            return self.last_run_at + timedelta(minutes=self.interval_minutes)
        else:
            return datetime.utcnow()


class TaskExecution(BaseModel, UUIDMixin, TimestampMixin):
    """
    Task execution history model.
    Records individual task executions for monitoring and debugging.
    """
    __tablename__ = 'task_executions'
    
    # Primary key
    id = Column(String, primary_key=True, default=lambda: TaskExecution.generate_id())
    
    # Foreign key
    task_name = Column(String, nullable=False, index=True)
    configuration_id = Column(String, nullable=True)  # May be null for ad-hoc executions
    
    # Execution details
    execution_id = Column(String, unique=True, index=True)  # Celery task ID
    status = Column(String, nullable=False, index=True)  # pending, running, success, failed, retry
    
    # Timing
    started_at = Column(DateTime, nullable=False, index=True)
    completed_at = Column(DateTime, index=True)
    duration_seconds = Column(Float)
    
    # Results
    result = Column(JSON)  # Task result data
    error_message = Column(Text)
    error_traceback = Column(Text)
    
    # Execution context
    worker_name = Column(String)
    retry_count = Column(Integer, default=0)
    parameters = Column(JSON)  # Parameters used for this execution
    
    # Relationships
    configuration = relationship("TaskConfiguration", back_populates="executions")
    
    def __repr__(self) -> str:
        return f"<TaskExecution(id='{self.id}', task='{self.task_name}', status='{self.status}')>"
    
    @property
    def is_running(self) -> bool:
        """Check if execution is currently running."""
        return self.status in ['pending', 'running']
    
    @property
    def is_completed(self) -> bool:
        """Check if execution is completed (success or failed)."""
        return self.status in ['success', 'failed']
    
    @property
    def is_successful(self) -> bool:
        """Check if execution was successful."""
        return self.status == 'success'
    
    @property
    def is_failed(self) -> bool:
        """Check if execution failed."""
        return self.status == 'failed'
    
    @property
    def execution_time_str(self) -> str:
        """Get formatted execution time."""
        if not self.duration_seconds:
            return "N/A"
        
        if self.duration_seconds < 60:
            return f"{self.duration_seconds:.1f}s"
        elif self.duration_seconds < 3600:
            minutes = self.duration_seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = self.duration_seconds / 3600
            return f"{hours:.1f}h"
    
    def start_execution(self, execution_id: str, worker_name: str = None, 
                       parameters: Dict[str, Any] = None) -> None:
        """Mark execution as started."""
        self.execution_id = execution_id
        self.status = 'running'
        self.started_at = datetime.utcnow()
        self.worker_name = worker_name
        self.parameters = parameters
    
    def complete_success(self, result: Dict[str, Any] = None) -> None:
        """Mark execution as successfully completed."""
        self.status = 'success'
        self.completed_at = datetime.utcnow()
        self.result = result
        self._calculate_duration()
    
    def complete_failure(self, error_message: str, error_traceback: str = None) -> None:
        """Mark execution as failed."""
        self.status = 'failed'
        self.completed_at = datetime.utcnow()
        self.error_message = error_message
        self.error_traceback = error_traceback
        self._calculate_duration()
    
    def increment_retry(self) -> None:
        """Increment retry count."""
        self.retry_count += 1
        self.status = 'retry'
    
    def _calculate_duration(self) -> None:
        """Calculate execution duration."""
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            self.duration_seconds = delta.total_seconds()


class TaskMetrics(BaseModel, TimestampMixin):
    """
    Task metrics model.
    Stores aggregated metrics for task performance monitoring.
    """
    __tablename__ = 'task_metrics'
    
    # Composite primary key
    task_name = Column(String, primary_key=True)
    date = Column(DateTime, primary_key=True)  # Date for daily aggregation
    
    # Execution counts
    total_executions = Column(Integer, default=0, nullable=False)
    successful_executions = Column(Integer, default=0, nullable=False)
    failed_executions = Column(Integer, default=0, nullable=False)
    
    # Timing metrics
    avg_duration_seconds = Column(Float)
    min_duration_seconds = Column(Float)
    max_duration_seconds = Column(Float)
    
    # Error tracking
    unique_errors = Column(Integer, default=0, nullable=False)
    most_common_error = Column(String)
    
    def __repr__(self) -> str:
        return f"<TaskMetrics(task='{self.task_name}', date='{self.date.date()}', executions={self.total_executions})>"
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_executions == 0:
            return 0.0
        return self.successful_executions / self.total_executions
    
    @property
    def failure_rate(self) -> float:
        """Calculate failure rate."""
        return 1.0 - self.success_rate
    
    def update_metrics(self, executions: list) -> None:
        """Update metrics from list of executions."""
        if not executions:
            return
        
        self.total_executions = len(executions)
        self.successful_executions = sum(1 for ex in executions if ex.is_successful)
        self.failed_executions = sum(1 for ex in executions if ex.is_failed)
        
        # Calculate timing metrics
        durations = [ex.duration_seconds for ex in executions if ex.duration_seconds is not None]
        if durations:
            self.avg_duration_seconds = sum(durations) / len(durations)
            self.min_duration_seconds = min(durations)
            self.max_duration_seconds = max(durations)
        
        # Error analysis
        errors = [ex.error_message for ex in executions if ex.error_message]
        self.unique_errors = len(set(errors))
        if errors:
            # Find most common error
            error_counts = {}
            for error in errors:
                error_counts[error] = error_counts.get(error, 0) + 1
            self.most_common_error = max(error_counts, key=error_counts.get)
