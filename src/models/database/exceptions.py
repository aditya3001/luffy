"""
Exception and RCA database models.
Handles exception clusters, root cause analysis results, and user feedback.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, String, Integer, Float, Boolean, Text, JSON, ForeignKey, DateTime
from sqlalchemy.orm import relationship

from .base import BaseModel, UUIDMixin, TimestampMixin


class ExceptionCluster(BaseModel, UUIDMixin, TimestampMixin):
    """
    Exception cluster metadata model.
    Groups similar exceptions together for analysis.
    """
    __tablename__ = 'exception_clusters'
    
    # Primary key
    cluster_id = Column(String, primary_key=True, default=lambda: ExceptionCluster.generate_id())
    
    # Foreign keys
    service_id = Column(String, ForeignKey('services.id'), nullable=False, index=True)
    log_source_id = Column(String, ForeignKey('log_sources.id'), nullable=False, index=True)
    
    # Exception details
    exception_type = Column(String, nullable=False, index=True)
    exception_message = Column(Text)
    
    # Fingerprinting
    fingerprint_static = Column(String, nullable=False, unique=True, index=True)  # Hash-based fingerprint
    fingerprint_semantic = Column(String, index=True)  # Embedding ID in vector DB
    
    # Representative exception
    representative_log_id = Column(String)
    stack_trace = Column(JSON)  # List of stack trace frames
    
    # Clustering metadata
    cluster_size = Column(Integer, default=1, nullable=False)
    first_seen = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    last_seen = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    frequency_24h = Column(Integer, default=0, nullable=False)
    frequency_7d = Column(Integer, default=0, nullable=False)
    
    # Analysis status
    has_rca = Column(Boolean, default=False, nullable=False)
    rca_generated_at = Column(DateTime)
    
    # Exception lifecycle status
    status = Column(String, default='active', nullable=False, index=True)  # active, skipped, resolved
    status_updated_at = Column(DateTime)
    status_updated_by = Column(String)  # user_id or system
    
    # Relationships
    service = relationship("Service", back_populates="clusters")
    log_source = relationship("LogSource", back_populates="clusters")
    rca_results = relationship(
        "RCAResult", 
        back_populates="cluster",
        cascade="all, delete-orphan"
    )
    feedbacks = relationship(
        "Feedback", 
        back_populates="cluster",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<ExceptionCluster(id='{self.cluster_id}', type='{self.exception_type}', status='{self.status}')>"
    
    @property
    def is_active(self) -> bool:
        """Check if the cluster is active."""
        return self.status == 'active'
    
    @property
    def is_resolved(self) -> bool:
        """Check if the cluster is resolved."""
        return self.status == 'resolved'
    
    @property
    def is_skipped(self) -> bool:
        """Check if the cluster is skipped."""
        return self.status == 'skipped'
    
    @property
    def latest_rca(self) -> Optional['RCAResult']:
        """Get the latest RCA result for this cluster."""
        if not self.rca_results:
            return None
        return max(self.rca_results, key=lambda rca: rca.created_at)
    
    @property
    def average_feedback_score(self) -> Optional[float]:
        """Calculate average feedback score for this cluster."""
        if not self.feedbacks:
            return None
        
        ratings = [f.accuracy_rating for f in self.feedbacks if f.accuracy_rating is not None]
        return sum(ratings) / len(ratings) if ratings else None
    
    def update_frequency(self, count_24h: int, count_7d: int) -> None:
        """Update frequency counters."""
        self.frequency_24h = count_24h
        self.frequency_7d = count_7d
        self.last_seen = datetime.utcnow()
    
    def increment_cluster_size(self, count: int = 1) -> None:
        """Increment cluster size."""
        self.cluster_size += count
        self.last_seen = datetime.utcnow()
    
    def mark_rca_generated(self) -> None:
        """Mark that RCA has been generated."""
        self.has_rca = True
        self.rca_generated_at = datetime.utcnow()
    
    def set_status(self, status: str, updated_by: str) -> None:
        """Update cluster status."""
        if status not in ['active', 'skipped', 'resolved']:
            raise ValueError(f"Invalid status: {status}")
        
        self.status = status
        self.status_updated_at = datetime.utcnow()
        self.status_updated_by = updated_by
    
    def resolve(self, updated_by: str) -> None:
        """Mark cluster as resolved."""
        self.set_status('resolved', updated_by)
    
    def skip(self, updated_by: str) -> None:
        """Mark cluster as skipped."""
        self.set_status('skipped', updated_by)
    
    def reactivate(self, updated_by: str) -> None:
        """Reactivate cluster."""
        self.set_status('active', updated_by)


class RCAResult(BaseModel, UUIDMixin, TimestampMixin):
    """
    Root Cause Analysis results model.
    Stores the results of automated root cause analysis.
    """
    __tablename__ = 'rca_results'
    
    # Primary key
    id = Column(String, primary_key=True, default=lambda: RCAResult.generate_id())
    
    # Foreign key
    cluster_id = Column(String, ForeignKey('exception_clusters.cluster_id'), nullable=False, index=True)
    
    # Root cause identification
    root_cause_file = Column(String)
    root_cause_symbol = Column(String)
    root_cause_line_start = Column(Integer)
    root_cause_line_end = Column(Integer)
    confidence_score = Column(Float)
    explanation = Column(Text)
    
    # Involved parameters
    involved_parameters = Column(JSON)  # List of parameter names and values
    
    # Fix suggestions
    fix_suggestions = Column(JSON)  # List of suggestions
    tests_to_add = Column(JSON)  # List of test cases
    
    # Supporting evidence
    supporting_evidence = Column(JSON)  # Code blocks and context
    
    # LLM metadata
    llm_model = Column(String)
    llm_tokens_used = Column(Integer)
    llm_cost = Column(Float)
    
    # Validation
    is_validated = Column(Boolean, default=False)
    validation_score = Column(Float)  # User feedback aggregation
    
    # Relationships
    cluster = relationship("ExceptionCluster", back_populates="rca_results")
    feedbacks = relationship(
        "Feedback", 
        back_populates="rca",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<RCAResult(id='{self.id}', cluster='{self.cluster_id}', confidence={self.confidence_score})>"
    
    @property
    def is_high_confidence(self) -> bool:
        """Check if this is a high confidence RCA result."""
        return self.confidence_score is not None and self.confidence_score >= 0.8
    
    @property
    def feedback_count(self) -> int:
        """Get number of feedback entries for this RCA."""
        return len(self.feedbacks)
    
    @property
    def positive_feedback_ratio(self) -> Optional[float]:
        """Calculate ratio of positive feedback."""
        if not self.feedbacks:
            return None
        
        positive = sum(1 for f in self.feedbacks if f.is_helpful is True)
        return positive / len(self.feedbacks)
    
    def calculate_validation_score(self) -> None:
        """Calculate and update validation score based on feedback."""
        if not self.feedbacks:
            self.validation_score = None
            return
        
        # Weight different feedback types
        helpful_score = 0
        rating_score = 0
        total_weight = 0
        
        for feedback in self.feedbacks:
            if feedback.is_helpful is not None:
                helpful_score += 1 if feedback.is_helpful else -1
                total_weight += 1
            
            if feedback.accuracy_rating is not None:
                rating_score += (feedback.accuracy_rating - 3) / 2  # Normalize to -1 to 1
                total_weight += 1
        
        if total_weight > 0:
            self.validation_score = (helpful_score + rating_score) / total_weight
        else:
            self.validation_score = None
    
    def mark_validated(self) -> None:
        """Mark RCA as validated."""
        self.is_validated = True
        self.calculate_validation_score()


class Feedback(BaseModel, UUIDMixin, TimestampMixin):
    """
    User feedback model for RCA results.
    Stores user feedback to improve RCA quality.
    """
    __tablename__ = 'feedback'
    
    # Primary key
    id = Column(String, primary_key=True, default=lambda: Feedback.generate_id())
    
    # Foreign keys
    cluster_id = Column(String, ForeignKey('exception_clusters.cluster_id'), nullable=False, index=True)
    rca_id = Column(String, ForeignKey('rca_results.id'), nullable=False, index=True)
    
    # Feedback details
    is_helpful = Column(Boolean)
    accuracy_rating = Column(Integer)  # 1-5 scale
    comments = Column(Text)
    
    # User information (optional)
    user_id = Column(String)
    user_email = Column(String)
    
    # Relationships
    cluster = relationship("ExceptionCluster", back_populates="feedbacks")
    rca = relationship("RCAResult", back_populates="feedbacks")
    
    def __repr__(self) -> str:
        return f"<Feedback(id='{self.id}', helpful={self.is_helpful}, rating={self.accuracy_rating})>"
    
    @property
    def is_positive(self) -> bool:
        """Check if this is positive feedback."""
        return (
            (self.is_helpful is True) or 
            (self.accuracy_rating is not None and self.accuracy_rating >= 4)
        )
    
    @property
    def is_negative(self) -> bool:
        """Check if this is negative feedback."""
        return (
            (self.is_helpful is False) or 
            (self.accuracy_rating is not None and self.accuracy_rating <= 2)
        )
    
    def validate_rating(self) -> None:
        """Validate accuracy rating is within valid range."""
        if self.accuracy_rating is not None:
            if not (1 <= self.accuracy_rating <= 5):
                raise ValueError("Accuracy rating must be between 1 and 5")
