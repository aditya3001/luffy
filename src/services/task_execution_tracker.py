"""
Task execution tracking utilities.
Provides functions to record and query task execution history.
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging
from sqlalchemy.orm import Session
from src.storage.database import get_db
from src.storage.models import TaskExecution, Service

logger = logging.getLogger(__name__)


def record_task_start(service_id: str, task_name: str) -> int:
    """
    Record the start of a task execution.
    
    Args:
        service_id: Service ID
        task_name: Task name ('log_fetch', 'rca_generation', 'code_indexing', 'cleanup')
    
    Returns:
        Task execution ID
    """
    with get_db() as db:
        execution = TaskExecution(
            service_id=service_id,
            task_name=task_name,
            started_at=datetime.utcnow(),
            status='running'
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)
        logger.info(f"Started task execution: {task_name} for service {service_id} (ID: {execution.id})")
        return execution.id


def record_task_completion(
    execution_id: int,
    status: str,
    stats: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None
):
    """
    Record the completion of a task execution.
    
    Args:
        execution_id: Task execution ID
        status: 'success' or 'failed'
        stats: Task-specific statistics
        error_message: Error message if failed
    """
    with get_db() as db:
        execution = db.query(TaskExecution).filter(TaskExecution.id == execution_id).first()
        if execution:
            execution.completed_at = datetime.utcnow()
            execution.status = status
            execution.stats = stats
            execution.error_message = error_message
            db.commit()
            logger.info(f"Completed task execution {execution_id}: {status}")


def get_last_execution(service_id: str, task_name: str) -> Optional[datetime]:
    """
    Get the timestamp of the last successful execution of a task.
    
    Args:
        service_id: Service ID
        task_name: Task name
    
    Returns:
        Datetime of last execution or None
    """
    with get_db() as db:
        execution = db.query(TaskExecution).filter(
            TaskExecution.service_id == service_id,
            TaskExecution.task_name == task_name,
            TaskExecution.status == 'success'
        ).order_by(TaskExecution.completed_at.desc()).first()
        
        if execution and execution.completed_at:
            return execution.completed_at
        return None


def calculate_next_run(
    last_run: Optional[datetime],
    interval_minutes: Optional[int] = None,
    cron_expr: Optional[str] = None
) -> Optional[datetime]:
    """
    Calculate the next scheduled run time based on interval or cron expression.
    
    Args:
        last_run: Last execution time
        interval_minutes: Interval in minutes (for interval-based scheduling)
        cron_expr: Cron expression (for time-based scheduling)
    
    Returns:
        Next scheduled run time or None
    """
    if cron_expr:
        # Cron-based scheduling
        try:
            from croniter import croniter
            base = last_run or datetime.utcnow()
            cron = croniter(cron_expr, base)
            return cron.get_next(datetime)
        except Exception as e:
            logger.error(f"Error parsing cron expression '{cron_expr}': {e}")
            return None
    elif interval_minutes:
        # Interval-based scheduling
        base = last_run or datetime.utcnow()
        return base + timedelta(minutes=interval_minutes)
    
    return None


def get_task_stats(service_id: str, task_name: str, hours: int = 24) -> Dict[str, Any]:
    """
    Get statistics for a task over the specified time period.
    
    Args:
        service_id: Service ID
        task_name: Task name
        hours: Number of hours to look back
    
    Returns:
        Dictionary with task statistics
    """
    with get_db() as db:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        executions = db.query(TaskExecution).filter(
            TaskExecution.service_id == service_id,
            TaskExecution.task_name == task_name,
            TaskExecution.started_at >= cutoff
        ).all()
        
        total = len(executions)
        successful = sum(1 for e in executions if e.status == 'success')
        failed = sum(1 for e in executions if e.status == 'failed')
        running = sum(1 for e in executions if e.status == 'running')
        
        return {
            'total_executions': total,
            'successful': successful,
            'failed': failed,
            'running': running,
            'success_rate': (successful / total * 100) if total > 0 else 0
        }


def update_service_last_run(service_id: str, task_name: str, timestamp: datetime):
    """
    Update the last run timestamp in the Service model.
    
    Args:
        service_id: Service ID
        task_name: Task name
        timestamp: Timestamp to set
    """
    with get_db() as db:
        service = db.query(Service).filter(Service.id == service_id).first()
        if service:
            if task_name == 'log_fetch':
                service.last_log_fetch = timestamp
            elif task_name == 'rca_generation':
                service.last_rca_generation = timestamp
            elif task_name == 'code_indexing':
                service.last_code_indexing = timestamp
            db.commit()
            logger.info(f"Updated {task_name} last run for service {service_id}")
