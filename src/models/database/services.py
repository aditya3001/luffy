"""
Service and Log Source database models.
Handles service management and log source configurations.
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, String, Integer, Boolean, Text, JSON, ForeignKey, DateTime
from sqlalchemy.orm import relationship

from .base import BaseModel, UUIDMixin, TimestampMixin


class Service(BaseModel, UUIDMixin, TimestampMixin):
    """
    Service/Application metadata model.
    Represents a service or application that generates logs.
    """
    __tablename__ = 'services'
    
    # Primary key
    id = Column(String, primary_key=True, default=lambda: Service.generate_id())
    
    # Basic information
    name = Column(String, nullable=False, unique=True, index=True)
    description = Column(Text)
    version = Column(String)
    
    # Repository information
    repository_url = Column(String)
    commit_sha = Column(String)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    log_sources = relationship(
        "LogSource", 
        back_populates="service", 
        cascade="all, delete-orphan",
        lazy="select"
    )
    clusters = relationship(
        "ExceptionCluster", 
        back_populates="service",
        lazy="select"
    )
    
    def __repr__(self) -> str:
        return f"<Service(id='{self.id}', name='{self.name}', active={self.is_active})>"
    
    @property
    def active_log_sources(self) -> List['LogSource']:
        """Get all active log sources for this service."""
        return [ls for ls in self.log_sources if ls.is_active]
    
    @property
    def total_clusters(self) -> int:
        """Get total number of exception clusters for this service."""
        return len(self.clusters)
    
    def activate(self) -> None:
        """Activate the service."""
        self.is_active = True
    
    def deactivate(self) -> None:
        """Deactivate the service."""
        self.is_active = False


class LogSource(BaseModel, UUIDMixin, TimestampMixin):
    """
    Log source configuration model.
    Represents a specific log source (OpenSearch, Elasticsearch, etc.) for a service.
    """
    __tablename__ = 'log_sources'
    
    # Primary key
    id = Column(String, primary_key=True, default=lambda: LogSource.generate_id())
    
    # Foreign key to service
    service_id = Column(String, ForeignKey('services.id'), nullable=False, index=True)
    
    # Basic information
    name = Column(String, nullable=False)
    source_type = Column(String, nullable=False)  # opensearch, elasticsearch, loki, cloudwatch, splunk
    
    # Connection configuration
    host = Column(String, nullable=False)
    port = Column(Integer, default=9200)
    username = Column(String)
    password = Column(String)  # Should be encrypted in production
    use_ssl = Column(Boolean, default=True)
    verify_certs = Column(Boolean, default=True)
    
    # Index/query configuration
    index_pattern = Column(String, nullable=False)
    query_filter = Column(JSON)  # Additional filters as JSON
    
    # Task configuration
    is_active = Column(Boolean, default=True, nullable=False)
    fetch_enabled = Column(Boolean, default=True, nullable=False)
    fetch_interval_minutes = Column(Integer, default=30)
    
    # Status tracking
    connection_status = Column(String, default='unknown')  # connected, disconnected, error
    last_connection_test = Column(DateTime)
    last_fetch_at = Column(DateTime)
    last_error = Column(Text)
    
    # Relationships
    service = relationship("Service", back_populates="log_sources")
    clusters = relationship(
        "ExceptionCluster", 
        back_populates="log_source",
        lazy="select"
    )
    
    def __repr__(self) -> str:
        return f"<LogSource(id='{self.id}', name='{self.name}', type='{self.source_type}')>"
    
    @property
    def connection_url(self) -> str:
        """Get the full connection URL."""
        protocol = "https" if self.use_ssl else "http"
        auth = f"{self.username}:{self.password}@" if self.username else ""
        return f"{protocol}://{auth}{self.host}:{self.port}"
    
    @property
    def is_connected(self) -> bool:
        """Check if the log source is currently connected."""
        return self.connection_status == 'connected'
    
    @property
    def total_clusters(self) -> int:
        """Get total number of exception clusters from this log source."""
        return len(self.clusters)
    
    def mark_connected(self) -> None:
        """Mark the log source as connected."""
        self.connection_status = 'connected'
        self.last_connection_test = datetime.utcnow()
        self.last_error = None
    
    def mark_disconnected(self, error: Optional[str] = None) -> None:
        """Mark the log source as disconnected."""
        self.connection_status = 'disconnected'
        self.last_connection_test = datetime.utcnow()
        if error:
            self.last_error = error
    
    def mark_error(self, error: str) -> None:
        """Mark the log source as having an error."""
        self.connection_status = 'error'
        self.last_connection_test = datetime.utcnow()
        self.last_error = error
    
    def update_fetch_time(self) -> None:
        """Update the last fetch timestamp."""
        self.last_fetch_at = datetime.utcnow()
    
    def enable_fetch(self) -> None:
        """Enable log fetching for this source."""
        self.fetch_enabled = True
    
    def disable_fetch(self) -> None:
        """Disable log fetching for this source."""
        self.fetch_enabled = False
    
    def activate(self) -> None:
        """Activate the log source."""
        self.is_active = True
    
    def deactivate(self) -> None:
        """Deactivate the log source."""
        self.is_active = False
        self.fetch_enabled = False
