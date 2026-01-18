"""
Database models for PostgreSQL storage.
Stores metadata about clusters, RCA results, and feedback.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, JSON, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Service(Base):
    """Service/Application metadata"""
    __tablename__ = 'services'
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(Text)
    version = Column(String)
    commit_sha = Column(String)
    
    # Git Configuration (per service)
    repository_url = Column(String)  # Git repository URL (https://github.com/org/repo.git)
    git_provider = Column(String)  # github, gitlab, bitbucket
    git_branch = Column(String, default='main')  # Branch to index
    git_repo_path = Column(String)  # Local path for cloned repo (only for local mode)
    access_token = Column(String)  # Access token for private repos (encrypted)
    use_api_mode = Column(Boolean, default=False)  # True: API mode (in-memory), False: Local mode (clone to disk)
    
    # Processing Configuration
    log_processing_enabled = Column(Boolean, default=True)  # Master toggle for log processing
    
    # Log fetch duration - time range to search in OpenSearch (in minutes)
    log_fetch_duration_minutes = Column(Integer, default=30)  # How far back to search logs
    log_fetch_duration_hours = Column(Integer)  # Alternative: duration in hours
    log_fetch_duration_days = Column(Integer)  # Alternative: duration in days
    
    rca_generation_enabled = Column(Boolean, default=True)
    rca_generation_interval_minutes = Column(Integer, default=15)
    code_indexing_enabled = Column(Boolean, default=True)
    
    # Notification Configuration
    notification_enabled = Column(Boolean, default=True)
    notification_webhook_url = Column(String)
    notification_email = Column(String)
    
    # Status
    is_active = Column(Boolean, default=True)
    last_log_fetch = Column(DateTime)
    last_rca_generation = Column(DateTime)
    
    # Code Indexing Status (On-Demand)
    code_indexing_status = Column(String, default='not_indexed')  # not_indexed, indexing, completed, failed
    code_indexing_trigger = Column(String)  # exception_detected, pre_rca, manual, webhook
    last_code_indexing = Column(DateTime)
    last_indexed_commit = Column(String)  # Git commit SHA
    code_indexing_error = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    log_sources = relationship("LogSource", back_populates="service", cascade="all, delete-orphan")
    clusters = relationship("ExceptionCluster", back_populates="service")
    indexing_metadata = relationship("IndexingMetadata", back_populates="service", cascade="all, delete-orphan")


class LogSource(Base):
    """Log source configuration for services"""
    __tablename__ = 'log_sources'
    
    id = Column(String, primary_key=True)
    service_id = Column(String, ForeignKey('services.id'), nullable=False)
    name = Column(String, nullable=False)
    source_type = Column(String, nullable=False)  # opensearch, elasticsearch, loki, etc.
    
    # Connection configuration
    host = Column(String, nullable=False)
    port = Column(Integer, default=9200)
    username = Column(String)
    password = Column(String)
    use_ssl = Column(Boolean, default=True)
    verify_certs = Column(Boolean, default=True)
    
    # Index/query configuration
    index_pattern = Column(String, nullable=False)
    query_filter = Column(JSON)  # Additional filters
    
    # Task configuration
    is_active = Column(Boolean, default=True)
    fetch_enabled = Column(Boolean, default=True)
    fetch_interval_minutes = Column(Integer, default=30)
    
    # Status
    connection_status = Column(String, default='unknown')  # connected, disconnected, error
    last_connection_test = Column(DateTime)
    last_fetch_at = Column(DateTime)
    last_error = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    service = relationship("Service", back_populates="log_sources")
    clusters = relationship("ExceptionCluster", back_populates="log_source")


class ExceptionCluster(Base):
    """Exception cluster metadata"""
    __tablename__ = 'exception_clusters'
    
    cluster_id = Column(String, primary_key=True)
    service_id = Column(String, ForeignKey('services.id'), nullable=False)
    log_source_id = Column(String, ForeignKey('log_sources.id'), nullable=False)
    exception_type = Column(String, nullable=False)
    exception_message = Column(Text)
    fingerprint_static = Column(String, nullable=False)  # Hash-based fingerprint
    fingerprint_semantic = Column(String)  # Embedding ID in vector DB
    
    # Representative exception
    representative_log_id = Column(String)
    stack_trace = Column(JSON)  # List of frames
    logger_path = Column(String)  # Logger path from log entry (e.g., com.company.service.ClassName)
    
    # Clustering metadata
    cluster_size = Column(Integer, default=1)
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    frequency_24h = Column(Integer, default=0)
    frequency_7d = Column(Integer, default=0)
    
    # Analysis status
    has_rca = Column(Boolean, default=False)
    rca_generated_at = Column(DateTime)
    
    # Exception lifecycle status
    status = Column(String, default='active')  # active, skipped, resolved
    status_updated_at = Column(DateTime)
    status_updated_by = Column(String)  # user_id or system
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    service = relationship("Service", back_populates="clusters")
    log_source = relationship("LogSource", back_populates="clusters")
    rca_results = relationship("RCAResult", back_populates="cluster")
    feedbacks = relationship("Feedback", back_populates="cluster")


class RCAResult(Base):
    """Root Cause Analysis results"""
    __tablename__ = 'rca_results'
    
    id = Column(String, primary_key=True)
    cluster_id = Column(String, ForeignKey('exception_clusters.cluster_id'), nullable=False)
    
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
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    cluster = relationship("ExceptionCluster", back_populates="rca_results")
    feedbacks = relationship("Feedback", back_populates="rca")


class Feedback(Base):
    """User feedback on RCA results"""
    __tablename__ = 'feedback'
    
    id = Column(String, primary_key=True)
    cluster_id = Column(String, ForeignKey('exception_clusters.cluster_id'), nullable=False)
    rca_id = Column(String, ForeignKey('rca_results.id'), nullable=False)
    
    # Feedback details
    is_helpful = Column(Boolean)
    accuracy_rating = Column(Integer)  # 1-5 scale
    comments = Column(Text)
    
    # User info (optional)
    user_id = Column(String)
    user_email = Column(String)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    cluster = relationship("ExceptionCluster", back_populates="feedbacks")
    rca = relationship("RCAResult", back_populates="feedbacks")


class CodeBlock(Base):
    """Indexed code blocks for context retrieval"""
    __tablename__ = 'code_blocks'
    
    id = Column(String, primary_key=True)
    repository = Column(String, nullable=False)
    version = Column(String, nullable=False)
    commit_sha = Column(String, nullable=False)
    
    file_path = Column(String, nullable=False)
    symbol_name = Column(String, nullable=False)  # Fully qualified name
    symbol_type = Column(String)  # function, class, method
    
    line_start = Column(Integer, nullable=False)
    line_end = Column(Integer, nullable=False)
    
    code_snippet = Column(Text, nullable=False)
    docstring = Column(Text)
    function_signature = Column(String)
    service_id = Column(String)
    
    # Vector embedding reference
    embedding_id = Column(String)  # ID in vector database
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CodeChange(Base):
    """Git commit tracking for code changes"""
    __tablename__ = 'code_changes'
    
    commit_sha = Column(String, primary_key=True)
    author = Column(String, nullable=False)
    author_email = Column(String)
    committer = Column(String)
    committer_email = Column(String)
    message = Column(Text, nullable=False)
    summary = Column(String)  # First line of commit message
    committed_date = Column(DateTime, nullable=False)
    authored_date = Column(DateTime)
    
    # Change statistics
    files_changed = Column(Integer, default=0)
    insertions = Column(Integer, default=0)
    deletions = Column(Integer, default=0)
    
    # File details (JSON array of changed files)
    changed_files = Column(JSON)  # [{"path": "...", "change_type": "M", "insertions": 10, "deletions": 5}]
    
    # Parent commits
    parent_commits = Column(JSON)  # List of parent commit SHAs
    
    # Correlation with exceptions
    related_exceptions = Column(JSON)  # List of cluster_ids that may be related
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    exception_blames = relationship("ExceptionBlame", back_populates="code_change")


class ExceptionBlame(Base):
    """Blame analysis linking exceptions to code changes"""
    __tablename__ = 'exception_blames'
    
    id = Column(String, primary_key=True)
    cluster_id = Column(String, ForeignKey('exception_clusters.cluster_id'), nullable=False)
    commit_sha = Column(String, ForeignKey('code_changes.commit_sha'), nullable=False)
    
    # Stack trace information
    file_path = Column(String, nullable=False)
    line_number = Column(Integer)
    function_name = Column(String)
    
    # Blame details
    blame_author = Column(String)
    blame_date = Column(DateTime)
    blame_message = Column(Text)
    
    # Correlation metadata
    confidence_score = Column(Float)  # How confident we are this change caused the exception
    time_delta_hours = Column(Float)  # Hours between commit and exception
    is_direct_cause = Column(Boolean, default=False)  # True if file is in stack trace
    
    # Analysis
    analysis = Column(JSON)  # Detailed correlation analysis
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    cluster = relationship("ExceptionCluster")
    code_change = relationship("CodeChange", back_populates="exception_blames")


class IndexingMetadata(Base):
    """Track repository indexing state for incremental indexing"""
    __tablename__ = 'indexing_metadata'
    
    id = Column(String, primary_key=True)  # UUID
    service_id = Column(String, ForeignKey('services.id', ondelete='CASCADE'), nullable=False, index=True)
    repository = Column(String, nullable=False)  # Repository name/URL
    commit_sha = Column(String)  # Last commit SHA indexed (renamed from last_indexed_commit)
    indexed_at = Column(DateTime)  # When indexing completed (renamed from last_indexed_at)
    files_indexed = Column(Integer, default=0)  # Renamed from total_files_indexed
    code_blocks_created = Column(Integer, default=0)  # Renamed from total_blocks_indexed
    indexing_mode = Column(String)  # 'full', 'incremental', 'api', 'local'
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    service = relationship("Service", back_populates="indexing_metadata")
    
    # Legacy column aliases for backward compatibility
    @property
    def last_indexed_commit(self):
        return self.commit_sha
    
    @property
    def last_indexed_at(self):
        return self.indexed_at
    
    @property
    def total_files_indexed(self):
        return self.files_indexed
    
    @property
    def total_blocks_indexed(self):
        return self.code_blocks_created


class TaskExecution(Base):
    """Track task execution history for monitoring and debugging"""
    __tablename__ = 'task_executions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    service_id = Column(String, ForeignKey('services.id', ondelete='CASCADE'), nullable=False)
    task_name = Column(String, nullable=False)  # 'log_fetch', 'rca_generation', 'code_indexing', 'cleanup'
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime)
    status = Column(String, nullable=False)  # 'running', 'success', 'failed'
    error_message = Column(Text)
    stats = Column(JSON)  # Task-specific statistics (e.g., logs processed, RCAs generated)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    service = relationship("Service")
