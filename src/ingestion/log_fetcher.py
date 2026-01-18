"""
Generic log fetcher that supports multiple sources.
Acts as a facade for different log connectors.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from src.config import settings
from src.ingestion.log_parser import LogParser

logger = logging.getLogger(__name__)


class LogFetcher:
    """Unified interface for fetching logs from various sources"""
    
    def __init__(self, source: str = None):
        """
        Initialize log fetcher.
        
        Args:
            source: Log source type ('file', 'opensearch', 'cloudwatch', 'gcp')
                   Defaults to settings.log_source
        """
        self.source = source or settings.log_source
        self.connector = None
        
        # Initialize appropriate connector
        self._initialize_connector()
    
    def _initialize_connector(self):
        """Initialize the appropriate connector based on source"""
        
        if self.source == 'opensearch' or self.source == 'elasticsearch':
            try:
                from src.ingestion.opensearch_connector import OpenSearchConnector
                self.connector = OpenSearchConnector()
                logger.info(f"Initialized OpenSearch connector")
            except Exception as e:
                logger.error(f"Error initializing OpenSearch connector: {e}")
                raise
        
        elif self.source == 'file':
            logger.info("Using file-based log reading")
            self.connector = None  # File doesn't need a connector
        
        elif self.source == 'cloudwatch':
            logger.warning("CloudWatch connector not yet implemented")
            raise NotImplementedError("CloudWatch connector coming soon")
        
        elif self.source == 'gcp_logging':
            logger.warning("GCP Logging connector not yet implemented")
            raise NotImplementedError("GCP Logging connector coming soon")
        
        else:
            raise ValueError(f"Unknown log source: {self.source}")
    
    def fetch_logs(
        self,
        duration_seconds: int = None,
        log_levels: List[str] = None,
        services: List[str] = None,
        max_logs: int = 10000,
        file_path: str = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch logs from configured source.
        
        Args:
            duration_seconds: Seconds of logs to fetch (for time-series sources).
                            If not provided, uses settings.fetch_interval_hours converted to seconds
            log_levels: Filter by log levels
            services: Filter by services
            max_logs: Maximum logs to fetch
            file_path: Path to file (for file source)
        
        Returns:
            List of log entries
        """
        # Use new flexible duration configuration with backward compatibility
        duration_seconds = duration_seconds or (settings.fetch_interval_hours * 3600)
        log_levels = log_levels or settings.log_levels_list
        
        duration_minutes = duration_seconds / 60
        logger.info(f"Fetching logs from {self.source} (duration: {duration_minutes:.1f}m, {duration_seconds}s)")
        
        if self.source in ['opensearch', 'elasticsearch']:
            return self._fetch_from_opensearch(
                duration_seconds=duration_seconds,
                log_levels=log_levels,
                services=services,
                max_logs=max_logs
            )
        
        elif self.source == 'file':
            return self._fetch_from_file(file_path=file_path)
        
        else:
            raise NotImplementedError(f"Fetching from {self.source} not implemented")
    
    def _fetch_from_opensearch(
        self,
        duration_seconds: int,
        log_levels: List[str],
        services: List[str],
        max_logs: int
    ) -> List[Dict[str, Any]]:
        """Fetch logs from OpenSearch"""
        
        if not self.connector:
            raise RuntimeError("OpenSearch connector not initialized")
        
        logs = self.connector.fetch_logs(
            duration_seconds=duration_seconds,
            log_levels=log_levels,
            services=services,
            max_logs=max_logs
        )
        
        logger.info(f"Fetched {len(logs)} logs from OpenSearch")
        return logs
    
    def _fetch_from_file(self, file_path: str = None) -> List[Dict[str, Any]]:
        """Fetch logs from file"""
        
        if not file_path:
            raise ValueError("file_path is required for file source")
        
        parser = LogParser()
        logs = parser.parse_log_file(file_path)
        
        logger.info(f"Parsed {len(logs)} logs from file: {file_path}")
        return logs
    
    def get_log_count(self, duration_hours: int = 24) -> int:
        """Get count of available logs"""
        
        if self.source in ['opensearch', 'elasticsearch']:
            if self.connector:
                return self.connector.get_log_count(duration_hours=duration_hours)
        
        return 0
    
    def test_connection(self) -> bool:
        """Test connection to log source"""
        
        if self.source in ['opensearch', 'elasticsearch']:
            if self.connector:
                return self.connector.test_connection()
        
        elif self.source == 'file':
            return True  # File source always "connected"
        
        return False
