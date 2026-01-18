"""
Database models package.
Provides all database models for the Luffy observability platform.
"""

# Base classes
from .base import Base, BaseModel, UUIDMixin, TimestampMixin, SoftDeleteMixin, AuditMixin

# Service models
from .services import Service, LogSource

# Exception models
from .exceptions import ExceptionCluster, RCAResult, Feedback

# Git integration models
from .git import CodeChange, ExceptionBlame, CodeBlock, IndexingMetadata

# Task models
from .tasks import TaskConfiguration, TaskExecution, TaskMetrics

# Analytics models
from .analytics import (
    DashboardMetrics,
    ExceptionTrend,
    ServiceMetrics,
    AlertMetrics,
    UserActivity
)

# Export all models
__all__ = [
    # Base classes
    'Base',
    'BaseModel',
    'UUIDMixin',
    'TimestampMixin',
    'SoftDeleteMixin',
    'AuditMixin',
    
    # Service models
    'Service',
    'LogSource',
    
    # Exception models
    'ExceptionCluster',
    'RCAResult',
    'Feedback',
    
    # Git integration models
    'CodeChange',
    'ExceptionBlame',
    'CodeBlock',
    'IndexingMetadata',
    
    # Task models
    'TaskConfiguration',
    'TaskExecution',
    'TaskMetrics',
    
    # Analytics models
    'DashboardMetrics',
    'ExceptionTrend',
    'ServiceMetrics',
    'AlertMetrics',
    'UserActivity',
]