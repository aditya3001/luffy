"""
OpenSearch/Elasticsearch connector for fetching production logs.
Supports configurable time ranges and query filtering.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from opensearchpy import OpenSearch
from opensearchpy.helpers import scan
from src.config import settings
from src.ingestion.log_normalizer import LogNormalizer

logger = logging.getLogger(__name__)


class OpenSearchConnector:
    """Fetch logs from OpenSearch/Elasticsearch"""
    
    def __init__(
        self,
        url: str = None,
        host: str = None,
        port: int = None,
        index_pattern: str = None,
        username: str = None,
        password: str = None,
        use_ssl: bool = None,
        verify_certs: bool = None
    ):
        """
        Initialize OpenSearch connector.
        
        Args:
            url: OpenSearch URL (legacy, defaults to settings)
            host: OpenSearch host (e.g., 'opensearch.example.com')
            port: OpenSearch port (e.g., 9200)
            index_pattern: Index pattern to search (e.g., 'logs-*')
            username: Basic auth username (optional)
            password: Basic auth password (optional)
            use_ssl: Use SSL/TLS connection (defaults to True)
            verify_certs: Verify SSL certificates (defaults to True)
        """
        # Handle both legacy URL and new host/port parameters
        if host and port:
            protocol = 'https' if (use_ssl if use_ssl is not None else True) else 'http'
            self.url = f"{protocol}://{host}:{port}"
        else:
            self.url = url or settings.elasticsearch_url
        
        self.host = host
        self.port = port
        self.index_pattern = index_pattern or settings.elasticsearch_index
        self.use_ssl = use_ssl if use_ssl is not None else True
        self.verify_certs = verify_certs if verify_certs is not None else True
        
        # Initialize log normalizer
        self.normalizer = LogNormalizer()
        
        # Initialize OpenSearch client with security settings
        client_args = {
            'hosts': [self.url],
            'use_ssl': self.use_ssl,
            'verify_certs': self.verify_certs,
            'ssl_show_warn': False,  # Suppress SSL warnings in logs
            'timeout': 30,  # 30 second timeout
            'max_retries': 3,  # Retry failed requests
            'retry_on_timeout': True,
            'headers': {
                'Content-Type': 'application/json'
            }
        }
        
        # Add authentication if provided
        if username and password:
            client_args['http_auth'] = (username, password)
        
        self.client = OpenSearch(**client_args)
        
        # Test connection
        try:
            if self.client.ping():
                logger.info(f"Connected to OpenSearch at {self.url}")
            else:
                logger.warning(f"Could not ping OpenSearch at {self.url}")
        except Exception as e:
            logger.error(f"Error connecting to OpenSearch: {e}")
    
    def fetch_logs(
        self,
        duration_seconds: int = 86400,
        log_levels: List[str] = None,
        services: List[str] = None,
        max_logs: int = 10000,
        end_time: datetime = None,
        index_pattern: str = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch logs from OpenSearch for a specific duration.
        
        Args:
            duration_seconds: How many seconds back to fetch (default: 86400 = 24 hours)
            log_levels: Filter by log levels (e.g., ['ERROR', 'CRITICAL'])
            services: Filter by service names (optional)
            max_logs: Maximum number of logs to fetch
            end_time: End time for the query (defaults to now)
            index_pattern: Index pattern to search (overrides default)
        
        Returns:
            List of log entries
        """
        # Calculate time range
        end_time = end_time or datetime.utcnow()
        start_time = end_time - timedelta(seconds=duration_seconds)
        
        # Use provided index pattern or default
        search_index = index_pattern or self.index_pattern
        
        duration_minutes = duration_seconds / 60
        logger.info(f"Fetching logs from {start_time} to {end_time} ({duration_minutes:.1f} minutes) from index: {search_index}")
        
        # Build query
        query = self._build_query(
            start_time=start_time,
            end_time=end_time,
            log_levels=log_levels,
            services=services
        )
        logger.info(f"query {query}")
        # Fetch logs
        logs = []
        try:
            # Use scroll API for efficient pagination
            for hit in scan(
                self.client,
                index=search_index,
                query=query,
                size=1000,  # Batch size
                scroll='5m'
            ):
                log_entry = self._parse_hit(hit)
                if log_entry:
                    logs.append(log_entry)
                
                # Limit total logs
                if len(logs) >= max_logs:
                    logger.warning(f"Reached max_logs limit of {max_logs}")
                    break
            
            logger.info(f"Fetched {len(logs)} logs from OpenSearch")
            
            # Normalize logs to ensure consistent format
            normalized_logs = self.normalizer.normalize_logs(logs, source='opensearch')
            logger.info(f"Normalized {len(normalized_logs)} logs")
            
            return normalized_logs
        
        except Exception as e:
            logger.error(f"Error fetching logs from OpenSearch: {e}")
            return []
    
    def _build_query(
        self,
        start_time: datetime,
        end_time: datetime,
        log_levels: List[str] = None,
        services: List[str] = None
    ) -> Dict[str, Any]:
        """Build Elasticsearch query DSL"""
        
        # Base query with time range
        must_clauses = [
            {
                "range": {
                    "@timestamp": {
                        "gte": start_time.isoformat(),
                        "lte": end_time.isoformat(),
                        "format": "strict_date_optional_time"
                    }
                }
            }
        ]
        
        # Filter by log levels
        # if log_levels:
        #     must_clauses.append({
        #         "terms": {
        #             "level.keyword": log_levels
        #         }
        #     })
        
        # Filter by services
        if services:
            must_clauses.append({
                "terms": {
                    "service.keyword": services
                }
            })
        
        query = {
            "query": {
                "bool": {
                    "must": must_clauses
                }
            },
            "sort": [
                {"@timestamp": {"order": "desc"}}
            ],
            "_source": True  # Include all fields
        }
        
        return query
    
    def _parse_hit(self, hit: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse OpenSearch hit into flat log format.
        
        Simply unwraps _source and adds log_id from hit._id.
        The LogNormalizer will handle all field parsing and normalization.
        """
        try:
            source = hit.get('_source', {})
            
            # Start with a flat structure - unwrap all _source fields
            log_entry = {}
            
            # Copy all fields from _source to top level
            for key, value in source.items():
                if not key.startswith('_'):
                    log_entry[key] = value
            
            # Add log_id from hit._id
            if 'log_id' not in log_entry:
                log_entry['log_id'] = hit.get('_id', '')
            
            return log_entry
        
        except Exception as e:
            logger.error(f"Error parsing log hit: {e}")
            return None
    
    def test_connection(self) -> bool:
        """Test OpenSearch connection"""
        try:
            return self.client.ping()
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    def get_indices(self) -> List[str]:
        """Get list of available indices"""
        try:
            indices = self.client.indices.get_alias(index=self.index_pattern)
            return list(indices.keys())
        except Exception as e:
            logger.error(f"Error getting indices: {e}")
            return []
    
    def get_log_count(
        self,
        duration_hours: int = 24,
        log_levels: List[str] = None
    ) -> int:
        """Get count of logs matching criteria"""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=duration_hours)
        
        query = self._build_query(
            start_time=start_time,
            end_time=end_time,
            log_levels=log_levels
        )
        
        try:
            result = self.client.count(index=self.index_pattern, body=query)
            return result.get('count', 0)
        except Exception as e:
            logger.error(f"Error counting logs: {e}")
            return 0


