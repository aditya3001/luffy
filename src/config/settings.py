"""
Configuration management using Pydantic Settings.
Loads from environment variables and .env file.
"""
from typing import List, Literal, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from src.config.duration import Duration, parse_duration


class Settings(BaseSettings):
    """Application settings with validation"""
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore'
    )
    
    # Log Source
    log_source: Literal['elasticsearch', 'cloudwatch', 'gcp_logging', 'file', 'opensearch'] = Field(default='opensearch')
    elasticsearch_url: str = Field(default='http://localhost:9200')
    elasticsearch_index: str = Field(default='logs-*')
    aws_region: str = Field(default='us-east-1')
    cloudwatch_log_group: str = Field(default='/aws/ecs/production')
    gcp_project_id: str = Field(default='my-project')
    
    # Log Fetch Interval - Flexible duration configuration
    log_fetch_interval: Union[str, int] = Field(default="30m")
    
    # Code Repository
    git_repo_path: str = Field(default='/app/data/repos/your-repo')
    git_branch: str = Field(default='main')
    code_version: str = Field(default='latest')
    
    # Code Indexing Mode
    code_indexing_mode: Literal['local', 'api'] = Field(default='api')
    
    # LLM Configuration
    llm_provider: Literal['openai', 'anthropic', 'local'] = Field(default='openai')
    openai_api_key: str = Field(default='')
    anthropic_api_key: str = Field(default='')
    llm_model: str = Field(default='gpt-4-turbo-preview')
    llm_temperature: float = Field(default=0.2)
    llm_max_tokens: int = Field(default=2000)
    
    # Vector Database
    vector_db_type: Literal['qdrant', 'faiss'] = Field(default='qdrant')
    qdrant_host: str = Field(default='localhost')
    qdrant_port: int = Field(default=6333)
    qdrant_api_key: str = Field(default='')
    embedding_model: str = Field(default='sentence-transformers/all-MiniLM-L6-v2')
    embedding_dimension: int = Field(default=384)
    
    # Relational Database
    database_url: str = Field(default='postgresql://luffy_user:luffy_password@localhost:5432/observability')
    database_pool_size: int = Field(default=20)
    database_max_overflow: int = Field(default=40)
    
    # Time-Series Database
    clickhouse_url: str = Field(default='http://localhost:8123')
    clickhouse_database: str = Field(default='logs')
    
    # Redis Cache
    redis_url: str = Field(default='redis://localhost:6379/0')
    redis_host: str = Field(default='localhost')
    redis_port: int = Field(default=6379)
    redis_db: int = Field(default=0)
    redis_cache_ttl: int = Field(default=3600)
    
    # Object Storage
    storage_backend: Literal['s3', 'gcs', 'local'] = Field(default='local')
    s3_bucket: str = Field(default='luffy-logs')
    s3_region: str = Field(default='us-east-1')
    gcs_bucket: str = Field(default='luffy-logs')
    local_storage_path: str = Field(default='/app/data/storage')
    
    # API Configuration
    api_port: int = Field(default=8000)
    api_host: str = Field(default='0.0.0.0')
    api_workers: int = Field(default=4)
    api_reload: bool = Field(default=False)
    cors_origins: str = Field(default='http://localhost:3000,http://localhost:8000')
    
    # Fluent Bit Ingestion
    fluent_bit_api_token: str = Field(default='')
    fluent_bit_rate_limit: int = Field(default=10000)
    fluent_bit_batch_size_limit: int = Field(default=1000)
    fluent_bit_dedup_window_seconds: int = Field(default=600)
    
    # Dashboard
    dashboard_port: int = Field(default=3000)
    
    # Processing
    batch_size: int = Field(default=1000)
    max_workers: int = Field(default=4)
    clustering_threshold: float = Field(default=0.85)
    min_cluster_size: int = 2
    processing_log_levels: str = 'ERROR,CRITICAL'
    
    # Feature Flags
    enable_real_time_streaming: bool = False
    enable_code_indexing: bool = True
    enable_llm_analysis: bool = True
    enable_feedback_loop: bool = True
    enable_gchat_notifications: bool = True
    
    # Google Chat Notifications
    gchat_webhook_url: str = 'https://chat.googleapis.com/v1/spaces/AAQAE5lOdEE/messages?key=AIzaSyDdI0hCZtE6vySjMm-WEfRq3CPzqKqqsHI&token=VD3h0ThbEjCXXiOYI6zp0k5H2znZfV4EAJN1UvFMnIc'
    gchat_notification_threshold: int = 1  # Notify when cluster size >= this
    
    # Monitoring
    enable_metrics: bool = True
    metrics_port: int = 9090
    log_level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] = 'INFO'
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Convert CORS origins string to list"""
        return [origin.strip() for origin in self.cors_origins.split(',')]
    
    @property
    def log_levels_list(self) -> List[str]:
        """Convert log levels string to list"""
        return [level.strip() for level in self.processing_log_levels.split(',')]
    
    @property
    def fetch_interval_duration(self) -> Duration:
        """
        Get log fetch interval as a Duration object.
        
        Returns:
            Duration object representing the fetch interval
            
        Examples:
            settings.log_fetch_interval = "30m"
            settings.fetch_interval_duration.to_minutes() -> 30
            
            settings.log_fetch_interval = "2h"
            settings.fetch_interval_duration.to_hours() -> 2.0
        """
        return parse_duration(self.log_fetch_interval)
    
    @property
    def fetch_interval_hours(self) -> float:
        """
        Get log fetch interval in hours (for backward compatibility).
        
        Returns:
            Fetch interval in hours as a float
        """
        return self.fetch_interval_duration.to_hours()
    
    @property
    def fetch_interval_minutes(self) -> int:
        """
        Get log fetch interval in minutes.
        
        Returns:
            Fetch interval in minutes as an integer
        """
        return self.fetch_interval_duration.to_minutes()


# Global settings instance
settings = Settings()
