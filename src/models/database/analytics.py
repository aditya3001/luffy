"""
Analytics and statistics database models.
Handles dashboard metrics, trends, and reporting data.
"""
from datetime import datetime, date
from typing import Optional, Dict, Any, List
from sqlalchemy import Column, String, Integer, Float, Boolean, Text, JSON, DateTime, Date
from sqlalchemy.orm import relationship

from .base import BaseModel, TimestampMixin


class DashboardMetrics(BaseModel, TimestampMixin):
    """
    Dashboard metrics model.
    Stores daily aggregated metrics for dashboard display.
    """
    __tablename__ = 'dashboard_metrics'
    
    # Composite primary key
    date = Column(Date, primary_key=True)
    service_id = Column(String, primary_key=True, default='global')  # 'global' for system-wide metrics
    
    # Exception metrics
    total_exceptions = Column(Integer, default=0, nullable=False)
    active_exceptions = Column(Integer, default=0, nullable=False)
    resolved_exceptions = Column(Integer, default=0, nullable=False)
    skipped_exceptions = Column(Integer, default=0, nullable=False)
    
    # Cluster metrics
    total_clusters = Column(Integer, default=0, nullable=False)
    new_clusters = Column(Integer, default=0, nullable=False)
    clusters_with_rca = Column(Integer, default=0, nullable=False)
    
    # RCA metrics
    rca_generated = Column(Integer, default=0, nullable=False)
    rca_success_rate = Column(Float, default=0.0, nullable=False)
    avg_rca_confidence = Column(Float)
    
    # Performance metrics
    avg_processing_time = Column(Float)  # Average time to process exceptions
    avg_rca_time = Column(Float)  # Average time to generate RCA
    
    # System health
    system_health_score = Column(Float, default=1.0, nullable=False)  # 0.0 to 1.0
    active_services = Column(Integer, default=0, nullable=False)
    active_log_sources = Column(Integer, default=0, nullable=False)
    
    def __repr__(self) -> str:
        return f"<DashboardMetrics(date='{self.date}', service='{self.service_id}', exceptions={self.total_exceptions})>"
    
    @property
    def exception_resolution_rate(self) -> float:
        """Calculate exception resolution rate."""
        if self.total_exceptions == 0:
            return 0.0
        return self.resolved_exceptions / self.total_exceptions
    
    @property
    def rca_coverage_rate(self) -> float:
        """Calculate RCA coverage rate."""
        if self.total_clusters == 0:
            return 0.0
        return self.clusters_with_rca / self.total_clusters
    
    def update_exception_metrics(self, active: int, resolved: int, skipped: int) -> None:
        """Update exception metrics."""
        self.active_exceptions = active
        self.resolved_exceptions = resolved
        self.skipped_exceptions = skipped
        self.total_exceptions = active + resolved + skipped
    
    def update_cluster_metrics(self, total: int, new: int, with_rca: int) -> None:
        """Update cluster metrics."""
        self.total_clusters = total
        self.new_clusters = new
        self.clusters_with_rca = with_rca
    
    def calculate_health_score(self) -> float:
        """Calculate system health score based on various factors."""
        score = 1.0
        
        # Reduce score based on active exceptions
        if self.total_exceptions > 0:
            active_ratio = self.active_exceptions / self.total_exceptions
            score -= active_ratio * 0.3  # Max 30% reduction for active exceptions
        
        # Reduce score if RCA coverage is low
        rca_coverage = self.rca_coverage_rate
        if rca_coverage < 0.8:
            score -= (0.8 - rca_coverage) * 0.2  # Max 20% reduction for low RCA coverage
        
        # Reduce score if RCA success rate is low
        if self.rca_success_rate < 0.7:
            score -= (0.7 - self.rca_success_rate) * 0.2  # Max 20% reduction for low success rate
        
        self.system_health_score = max(0.0, score)
        return self.system_health_score


class ExceptionTrend(BaseModel, TimestampMixin):
    """
    Exception trend model.
    Stores hourly exception trends for charting and analysis.
    """
    __tablename__ = 'exception_trends'
    
    # Composite primary key
    timestamp = Column(DateTime, primary_key=True)  # Hourly timestamp
    service_id = Column(String, primary_key=True, default='global')
    log_source_id = Column(String, primary_key=True, default='global')
    
    # Exception counts
    exception_count = Column(Integer, default=0, nullable=False)
    new_clusters = Column(Integer, default=0, nullable=False)
    
    # Exception types breakdown
    exception_types = Column(JSON)  # {"TypeError": 5, "ValueError": 3, ...}
    
    # Severity breakdown
    severity_breakdown = Column(JSON)  # {"critical": 2, "high": 5, "medium": 8, ...}
    
    def __repr__(self) -> str:
        return f"<ExceptionTrend(timestamp='{self.timestamp}', service='{self.service_id}', count={self.exception_count})>"
    
    @property
    def hour(self) -> int:
        """Get hour of the day (0-23)."""
        return self.timestamp.hour
    
    @property
    def day_of_week(self) -> int:
        """Get day of week (0=Monday, 6=Sunday)."""
        return self.timestamp.weekday()
    
    def add_exception(self, exception_type: str, severity: str = 'medium') -> None:
        """Add an exception to the trend data."""
        self.exception_count += 1
        
        # Update exception types
        if not self.exception_types:
            self.exception_types = {}
        self.exception_types[exception_type] = self.exception_types.get(exception_type, 0) + 1
        
        # Update severity breakdown
        if not self.severity_breakdown:
            self.severity_breakdown = {}
        self.severity_breakdown[severity] = self.severity_breakdown.get(severity, 0) + 1
    
    def get_top_exception_types(self, limit: int = 5) -> List[tuple]:
        """Get top exception types by count."""
        if not self.exception_types:
            return []
        
        return sorted(self.exception_types.items(), key=lambda x: x[1], reverse=True)[:limit]


class ServiceMetrics(BaseModel, TimestampMixin):
    """
    Service-specific metrics model.
    Stores detailed metrics for individual services.
    """
    __tablename__ = 'service_metrics'
    
    # Composite primary key
    service_id = Column(String, primary_key=True)
    date = Column(Date, primary_key=True)
    
    # Exception metrics
    total_exceptions = Column(Integer, default=0, nullable=False)
    unique_exception_types = Column(Integer, default=0, nullable=False)
    avg_cluster_size = Column(Float, default=0.0, nullable=False)
    
    # Performance metrics
    mttr_hours = Column(Float)  # Mean Time To Resolution
    mtbf_hours = Column(Float)  # Mean Time Between Failures
    
    # Quality metrics
    false_positive_rate = Column(Float, default=0.0, nullable=False)
    rca_accuracy_score = Column(Float)  # Based on user feedback
    
    # Activity metrics
    log_sources_active = Column(Integer, default=0, nullable=False)
    data_volume_mb = Column(Float, default=0.0, nullable=False)
    
    def __repr__(self) -> str:
        return f"<ServiceMetrics(service='{self.service_id}', date='{self.date}', exceptions={self.total_exceptions})>"
    
    @property
    def exception_density(self) -> float:
        """Calculate exception density (exceptions per MB of logs)."""
        if self.data_volume_mb == 0:
            return 0.0
        return self.total_exceptions / self.data_volume_mb
    
    def update_performance_metrics(self, resolution_times: List[float]) -> None:
        """Update performance metrics from resolution times."""
        if not resolution_times:
            return
        
        self.mttr_hours = sum(resolution_times) / len(resolution_times)
    
    def update_quality_metrics(self, feedback_scores: List[float]) -> None:
        """Update quality metrics from user feedback."""
        if not feedback_scores:
            return
        
        self.rca_accuracy_score = sum(feedback_scores) / len(feedback_scores)


class AlertMetrics(BaseModel, TimestampMixin):
    """
    Alert metrics model.
    Tracks alerting effectiveness and noise levels.
    """
    __tablename__ = 'alert_metrics'
    
    # Composite primary key
    date = Column(Date, primary_key=True)
    alert_type = Column(String, primary_key=True)  # threshold, anomaly, pattern
    
    # Alert counts
    alerts_triggered = Column(Integer, default=0, nullable=False)
    alerts_acknowledged = Column(Integer, default=0, nullable=False)
    alerts_resolved = Column(Integer, default=0, nullable=False)
    false_positives = Column(Integer, default=0, nullable=False)
    
    # Timing metrics
    avg_response_time_minutes = Column(Float)
    avg_resolution_time_hours = Column(Float)
    
    def __repr__(self) -> str:
        return f"<AlertMetrics(date='{self.date}', type='{self.alert_type}', triggered={self.alerts_triggered})>"
    
    @property
    def acknowledgment_rate(self) -> float:
        """Calculate alert acknowledgment rate."""
        if self.alerts_triggered == 0:
            return 0.0
        return self.alerts_acknowledged / self.alerts_triggered
    
    @property
    def false_positive_rate(self) -> float:
        """Calculate false positive rate."""
        if self.alerts_triggered == 0:
            return 0.0
        return self.false_positives / self.alerts_triggered
    
    @property
    def resolution_rate(self) -> float:
        """Calculate alert resolution rate."""
        if self.alerts_triggered == 0:
            return 0.0
        return self.alerts_resolved / self.alerts_triggered


class UserActivity(BaseModel, TimestampMixin):
    """
    User activity model.
    Tracks user interactions with the system.
    """
    __tablename__ = 'user_activity'
    
    # Primary key
    id = Column(String, primary_key=True)
    
    # User information
    user_id = Column(String, nullable=False, index=True)
    user_email = Column(String, index=True)
    
    # Activity details
    action = Column(String, nullable=False, index=True)  # view_cluster, generate_rca, provide_feedback
    resource_type = Column(String, nullable=False)  # cluster, rca, service
    resource_id = Column(String, nullable=False)
    
    # Context
    session_id = Column(String, index=True)
    ip_address = Column(String)
    user_agent = Column(String)
    
    # Metadata
    metadata = Column(JSON)  # Additional context data
    
    def __repr__(self) -> str:
        return f"<UserActivity(user='{self.user_id}', action='{self.action}', resource='{self.resource_type}')>"
    
    @staticmethod
    def log_activity(user_id: str, action: str, resource_type: str, resource_id: str,
                    session_id: str = None, metadata: Dict[str, Any] = None) -> 'UserActivity':
        """Create a new user activity log entry."""
        return UserActivity(
            id=UserActivity.generate_id(),
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            session_id=session_id,
            metadata=metadata
        )
