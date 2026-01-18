"""
Git integration database models.
Handles code changes, blame analysis, and code indexing.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, String, Integer, Float, Boolean, Text, JSON, ForeignKey, DateTime
from sqlalchemy.orm import relationship

from .base import BaseModel, UUIDMixin, TimestampMixin


class CodeChange(BaseModel, TimestampMixin):
    """
    Git commit tracking model.
    Stores information about code changes from Git commits.
    """
    __tablename__ = 'code_changes'
    
    # Primary key (commit SHA)
    commit_sha = Column(String, primary_key=True)
    
    # Author information
    author = Column(String, nullable=False)
    author_email = Column(String)
    committer = Column(String)
    committer_email = Column(String)
    
    # Commit details
    message = Column(Text, nullable=False)
    summary = Column(String)  # First line of commit message
    committed_date = Column(DateTime, nullable=False, index=True)
    authored_date = Column(DateTime, index=True)
    
    # Change statistics
    files_changed = Column(Integer, default=0, nullable=False)
    insertions = Column(Integer, default=0, nullable=False)
    deletions = Column(Integer, default=0, nullable=False)
    
    # File details (JSON array of changed files)
    changed_files = Column(JSON)  # [{"path": "...", "change_type": "M", "insertions": 10, "deletions": 5}]
    
    # Parent commits
    parent_commits = Column(JSON)  # List of parent commit SHAs
    
    # Correlation with exceptions
    related_exceptions = Column(JSON)  # List of cluster_ids that may be related
    
    # Relationships
    exception_blames = relationship(
        "ExceptionBlame", 
        back_populates="code_change",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<CodeChange(sha='{self.commit_sha[:8]}', author='{self.author}', files={self.files_changed})>"
    
    @property
    def short_sha(self) -> str:
        """Get short commit SHA (first 8 characters)."""
        return self.commit_sha[:8] if self.commit_sha else ""
    
    @property
    def is_merge_commit(self) -> bool:
        """Check if this is a merge commit."""
        return len(self.parent_commits or []) > 1
    
    @property
    def change_magnitude(self) -> int:
        """Calculate total change magnitude."""
        return self.insertions + self.deletions
    
    @property
    def net_change(self) -> int:
        """Calculate net change (insertions - deletions)."""
        return self.insertions - self.deletions
    
    def get_changed_files_by_type(self, change_type: str) -> List[Dict[str, Any]]:
        """Get changed files by change type (A, M, D, R)."""
        if not self.changed_files:
            return []
        return [f for f in self.changed_files if f.get('change_type') == change_type]
    
    def get_file_extensions(self) -> List[str]:
        """Get unique file extensions from changed files."""
        if not self.changed_files:
            return []
        
        extensions = set()
        for file_info in self.changed_files:
            path = file_info.get('path', '')
            if '.' in path:
                ext = path.split('.')[-1].lower()
                extensions.add(ext)
        
        return list(extensions)
    
    def add_related_exception(self, cluster_id: str) -> None:
        """Add a related exception cluster ID."""
        if not self.related_exceptions:
            self.related_exceptions = []
        
        if cluster_id not in self.related_exceptions:
            self.related_exceptions.append(cluster_id)
    
    def remove_related_exception(self, cluster_id: str) -> None:
        """Remove a related exception cluster ID."""
        if self.related_exceptions and cluster_id in self.related_exceptions:
            self.related_exceptions.remove(cluster_id)


class ExceptionBlame(BaseModel, UUIDMixin, TimestampMixin):
    """
    Blame analysis model.
    Links exceptions to code changes through Git blame analysis.
    """
    __tablename__ = 'exception_blames'
    
    # Primary key
    id = Column(String, primary_key=True, default=lambda: ExceptionBlame.generate_id())
    
    # Foreign keys
    cluster_id = Column(String, ForeignKey('exception_clusters.cluster_id'), nullable=False, index=True)
    commit_sha = Column(String, ForeignKey('code_changes.commit_sha'), nullable=False, index=True)
    
    # Stack trace information
    file_path = Column(String, nullable=False, index=True)
    line_number = Column(Integer)
    function_name = Column(String)
    
    # Blame details
    blame_author = Column(String)
    blame_date = Column(DateTime, index=True)
    blame_message = Column(Text)
    
    # Correlation metadata
    confidence_score = Column(Float, index=True)  # How confident we are this change caused the exception
    time_delta_hours = Column(Float)  # Hours between commit and exception
    is_direct_cause = Column(Boolean, default=False, index=True)  # True if file is in stack trace
    
    # Analysis details
    analysis = Column(JSON)  # Detailed correlation analysis
    
    # Relationships
    cluster = relationship("ExceptionCluster")
    code_change = relationship("CodeChange", back_populates="exception_blames")
    
    def __repr__(self) -> str:
        return f"<ExceptionBlame(id='{self.id}', confidence={self.confidence_score}, direct={self.is_direct_cause})>"
    
    @property
    def is_high_confidence(self) -> bool:
        """Check if this is a high confidence blame result."""
        return self.confidence_score is not None and self.confidence_score >= 0.8
    
    @property
    def is_recent_change(self) -> bool:
        """Check if the change was recent (within 48 hours of exception)."""
        return self.time_delta_hours is not None and self.time_delta_hours <= 48
    
    @property
    def blame_summary(self) -> str:
        """Get a summary of the blame information."""
        parts = []
        if self.blame_author:
            parts.append(f"by {self.blame_author}")
        if self.blame_date:
            parts.append(f"on {self.blame_date.strftime('%Y-%m-%d')}")
        if self.function_name:
            parts.append(f"in {self.function_name}()")
        
        return " ".join(parts) if parts else "Unknown"
    
    def calculate_confidence_score(self) -> float:
        """Calculate confidence score based on various factors."""
        score = 0.0
        
        # Direct cause (file in stack trace) gets high score
        if self.is_direct_cause:
            score += 0.6
        
        # Recent changes get higher score
        if self.time_delta_hours is not None:
            if self.time_delta_hours <= 24:
                score += 0.3
            elif self.time_delta_hours <= 48:
                score += 0.2
            elif self.time_delta_hours <= 168:  # 1 week
                score += 0.1
        
        # Function name match gets bonus
        if self.function_name:
            score += 0.1
        
        return min(score, 1.0)  # Cap at 1.0
    
    def update_confidence_score(self) -> None:
        """Update the confidence score based on current data."""
        self.confidence_score = self.calculate_confidence_score()


class CodeBlock(BaseModel, UUIDMixin, TimestampMixin):
    """
    Indexed code blocks model.
    Stores indexed code blocks for context retrieval and analysis.
    """
    __tablename__ = 'code_blocks'
    
    # Primary key
    id = Column(String, primary_key=True, default=lambda: CodeBlock.generate_id())
    
    # Repository information
    repository = Column(String, nullable=False, index=True)
    version = Column(String, nullable=False)
    commit_sha = Column(String, nullable=False, index=True)
    
    # File and symbol information
    file_path = Column(String, nullable=False, index=True)
    symbol_name = Column(String, nullable=False, index=True)  # Fully qualified name
    symbol_type = Column(String, index=True)  # function, class, method, variable
    
    # Location information
    line_start = Column(Integer, nullable=False)
    line_end = Column(Integer, nullable=False)
    
    # Code content
    code_snippet = Column(Text, nullable=False)
    docstring = Column(Text)
    function_signature = Column(String)
    
    # Vector embedding reference
    embedding_id = Column(String, index=True)  # ID in vector database
    
    def __repr__(self) -> str:
        return f"<CodeBlock(id='{self.id}', symbol='{self.symbol_name}', type='{self.symbol_type}')>"
    
    @property
    def line_count(self) -> int:
        """Get number of lines in the code block."""
        return self.line_end - self.line_start + 1
    
    @property
    def file_name(self) -> str:
        """Get just the file name from the full path."""
        return self.file_path.split('/')[-1] if self.file_path else ""
    
    @property
    def is_function(self) -> bool:
        """Check if this is a function code block."""
        return self.symbol_type in ['function', 'method']
    
    @property
    def is_class(self) -> bool:
        """Check if this is a class code block."""
        return self.symbol_type == 'class'
    
    def get_qualified_name(self) -> str:
        """Get fully qualified symbol name including file."""
        return f"{self.file_path}:{self.symbol_name}"
    
    def is_in_line_range(self, line_number: int) -> bool:
        """Check if a line number is within this code block."""
        return self.line_start <= line_number <= self.line_end


class IndexingMetadata(BaseModel, TimestampMixin):
    """
    Repository indexing metadata model.
    Tracks the state of repository indexing for incremental updates.
    """
    __tablename__ = 'indexing_metadata'
    
    # Primary key (repository name)
    repository = Column(String, primary_key=True)
    
    # Indexing state
    last_indexed_commit = Column(String)  # Last commit SHA indexed
    last_indexed_at = Column(DateTime, index=True)  # When indexing completed
    
    # Statistics
    total_files_indexed = Column(Integer, default=0, nullable=False)
    total_blocks_indexed = Column(Integer, default=0, nullable=False)
    
    # Configuration
    indexing_mode = Column(String, default='incremental')  # 'full' or 'incremental'
    
    def __repr__(self) -> str:
        return f"<IndexingMetadata(repo='{self.repository}', commit='{self.last_indexed_commit[:8] if self.last_indexed_commit else None}')>"
    
    @property
    def is_fully_indexed(self) -> bool:
        """Check if repository has been fully indexed."""
        return self.last_indexed_commit is not None and self.last_indexed_at is not None
    
    @property
    def indexing_age_hours(self) -> Optional[float]:
        """Get age of last indexing in hours."""
        if not self.last_indexed_at:
            return None
        
        delta = datetime.utcnow() - self.last_indexed_at
        return delta.total_seconds() / 3600
    
    @property
    def needs_reindexing(self, max_age_hours: int = 24) -> bool:
        """Check if repository needs reindexing."""
        age = self.indexing_age_hours
        return age is None or age > max_age_hours
    
    def update_indexing_stats(self, commit_sha: str, files_count: int, blocks_count: int) -> None:
        """Update indexing statistics."""
        self.last_indexed_commit = commit_sha
        self.last_indexed_at = datetime.utcnow()
        self.total_files_indexed = files_count
        self.total_blocks_indexed = blocks_count
    
    def mark_full_indexing(self) -> None:
        """Mark as full indexing mode."""
        self.indexing_mode = 'full'
    
    def mark_incremental_indexing(self) -> None:
        """Mark as incremental indexing mode."""
        self.indexing_mode = 'incremental'
