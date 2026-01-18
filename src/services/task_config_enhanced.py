"""
Enhanced task configuration manager for multi-service architecture.
Supports per-service and per-log-source task management.
"""
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import redis
from src.config import settings

logger = logging.getLogger(__name__)

@dataclass
class LogSourceTaskConfig:
    """Configuration for a log source's tasks"""
    log_source_id: str
    service_id: str
    fetch_enabled: bool = True
    fetch_interval_minutes: int = 30
    last_fetch_at: Optional[str] = None
    last_error: Optional[str] = None
    modified_at: str = ""
    modified_by: str = "system"

@dataclass
class ServiceTaskConfig:
    """Configuration for service-level tasks"""
    service_id: str
    rca_enabled: bool = True
    rca_interval_minutes: int = 15
    index_code_enabled: bool = True
    index_code_cron: str = "0 2 * * *"  # Daily at 2 AM
    cleanup_enabled: bool = True
    cleanup_cron: str = "0 3 * * 0"  # Weekly on Sunday at 3 AM
    modified_at: str = ""
    modified_by: str = "system"

class EnhancedTaskConfigManager:
    """Enhanced task configuration manager with multi-service support"""
    
    def __init__(self):
        self.redis_client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            decode_responses=True
        )
        self.log_source_prefix = "luffy:log_source_task:"
        self.service_prefix = "luffy:service_task:"
        self.global_prefix = "luffy:global_task:"
    
    # ============================================================================
    # LOG SOURCE TASK MANAGEMENT
    # ============================================================================
    
    def get_log_source_config(self, log_source_id: str) -> LogSourceTaskConfig:
        """Get task configuration for a log source"""
        try:
            key = f"{self.log_source_prefix}{log_source_id}"
            config_data = self.redis_client.get(key)
            
            if config_data:
                data = json.loads(config_data)
                return LogSourceTaskConfig(**data)
            else:
                # Return default config
                return LogSourceTaskConfig(
                    log_source_id=log_source_id,
                    service_id="",  # Will be filled by caller
                    modified_at=datetime.utcnow().isoformat()
                )
        except Exception as e:
            logger.error(f"Error getting log source config {log_source_id}: {e}")
            return LogSourceTaskConfig(
                log_source_id=log_source_id,
                service_id="",
                modified_at=datetime.utcnow().isoformat()
            )
    
    def set_log_source_config(self, config: LogSourceTaskConfig) -> bool:
        """Set task configuration for a log source"""
        try:
            key = f"{self.log_source_prefix}{config.log_source_id}"
            config.modified_at = datetime.utcnow().isoformat()
            
            self.redis_client.set(key, json.dumps(asdict(config)))
            logger.info(f"Updated log source task config: {config.log_source_id}")
            return True
        except Exception as e:
            logger.error(f"Error setting log source config {config.log_source_id}: {e}")
            return False
    
    def enable_log_source_fetch(self, log_source_id: str, modified_by: str = "api") -> bool:
        """Enable log fetching for a log source"""
        config = self.get_log_source_config(log_source_id)
        config.fetch_enabled = True
        config.modified_by = modified_by
        return self.set_log_source_config(config)
    
    def disable_log_source_fetch(self, log_source_id: str, modified_by: str = "api") -> bool:
        """Disable log fetching for a log source"""
        config = self.get_log_source_config(log_source_id)
        config.fetch_enabled = False
        config.modified_by = modified_by
        return self.set_log_source_config(config)
    
    def update_log_source_interval(self, log_source_id: str, interval_minutes: int, modified_by: str = "api") -> bool:
        """Update fetch interval for a log source"""
        if interval_minutes < 1 or interval_minutes > 1440:  # 1 minute to 24 hours
            logger.error(f"Invalid interval: {interval_minutes}")
            return False
        
        config = self.get_log_source_config(log_source_id)
        config.fetch_interval_minutes = interval_minutes
        config.modified_by = modified_by
        return self.set_log_source_config(config)
    
    def record_log_source_fetch(self, log_source_id: str, success: bool, error: Optional[str] = None) -> bool:
        """Record the result of a log source fetch"""
        config = self.get_log_source_config(log_source_id)
        config.last_fetch_at = datetime.utcnow().isoformat()
        if not success and error:
            config.last_error = error
        elif success:
            config.last_error = None
        return self.set_log_source_config(config)
    
    def list_log_source_configs(self, service_id: Optional[str] = None) -> List[LogSourceTaskConfig]:
        """List all log source configurations, optionally filtered by service"""
        try:
            pattern = f"{self.log_source_prefix}*"
            keys = self.redis_client.keys(pattern)
            
            configs = []
            for key in keys:
                config_data = self.redis_client.get(key)
                if config_data:
                    data = json.loads(config_data)
                    config = LogSourceTaskConfig(**data)
                    
                    # Filter by service if specified
                    if service_id is None or config.service_id == service_id:
                        configs.append(config)
            
            return configs
        except Exception as e:
            logger.error(f"Error listing log source configs: {e}")
            return []
    
    # ============================================================================
    # SERVICE TASK MANAGEMENT
    # ============================================================================
    
    def get_service_config(self, service_id: str) -> ServiceTaskConfig:
        """Get task configuration for a service"""
        try:
            key = f"{self.service_prefix}{service_id}"
            config_data = self.redis_client.get(key)
            
            if config_data:
                data = json.loads(config_data)
                return ServiceTaskConfig(**data)
            else:
                # Return default config
                return ServiceTaskConfig(
                    service_id=service_id,
                    modified_at=datetime.utcnow().isoformat()
                )
        except Exception as e:
            logger.error(f"Error getting service config {service_id}: {e}")
            return ServiceTaskConfig(
                service_id=service_id,
                modified_at=datetime.utcnow().isoformat()
            )
    
    def set_service_config(self, config: ServiceTaskConfig) -> bool:
        """Set task configuration for a service"""
        try:
            key = f"{self.service_prefix}{config.service_id}"
            config.modified_at = datetime.utcnow().isoformat()
            
            self.redis_client.set(key, json.dumps(asdict(config)))
            logger.info(f"Updated service task config: {config.service_id}")
            return True
        except Exception as e:
            logger.error(f"Error setting service config {config.service_id}: {e}")
            return False
    
    def update_service_rca_config(self, service_id: str, enabled: bool, interval_minutes: int = 15, modified_by: str = "api") -> bool:
        """Update RCA configuration for a service"""
        config = self.get_service_config(service_id)
        config.rca_enabled = enabled
        config.rca_interval_minutes = interval_minutes
        config.modified_by = modified_by
        return self.set_service_config(config)
    
    def update_service_index_config(self, service_id: str, enabled: bool, cron: str = "0 2 * * *", modified_by: str = "api") -> bool:
        """Update code indexing configuration for a service"""
        config = self.get_service_config(service_id)
        config.index_code_enabled = enabled
        config.index_code_cron = cron
        config.modified_by = modified_by
        return self.set_service_config(config)
    
    def update_service_cleanup_config(self, service_id: str, enabled: bool, cron: str = "0 3 * * 0", modified_by: str = "api") -> bool:
        """Update cleanup configuration for a service"""
        config = self.get_service_config(service_id)
        config.cleanup_enabled = enabled
        config.cleanup_cron = cron
        config.modified_by = modified_by
        return self.set_service_config(config)
    
    def list_service_configs(self) -> List[ServiceTaskConfig]:
        """List all service configurations"""
        try:
            pattern = f"{self.service_prefix}*"
            keys = self.redis_client.keys(pattern)
            
            configs = []
            for key in keys:
                config_data = self.redis_client.get(key)
                if config_data:
                    data = json.loads(config_data)
                    configs.append(ServiceTaskConfig(**data))
            
            return configs
        except Exception as e:
            logger.error(f"Error listing service configs: {e}")
            return []
    
    # ============================================================================
    # GLOBAL TASK MANAGEMENT (backwards compatibility)
    # ============================================================================
    
    def is_global_task_enabled(self, task_name: str) -> bool:
        """Check if a global task is enabled (backwards compatibility)"""
        try:
            key = f"{self.global_prefix}{task_name}"
            config_data = self.redis_client.get(key)
            
            if config_data:
                config = json.loads(config_data)
                return config.get('enabled', True)
            
            return True  # Default to enabled
        except Exception as e:
            logger.error(f"Error checking global task {task_name}: {e}")
            return True
    
    def set_global_task_enabled(self, task_name: str, enabled: bool, modified_by: str = "api") -> bool:
        """Enable/disable a global task"""
        try:
            key = f"{self.global_prefix}{task_name}"
            config = {
                'enabled': enabled,
                'modified_at': datetime.utcnow().isoformat(),
                'modified_by': modified_by
            }
            
            self.redis_client.set(key, json.dumps(config))
            logger.info(f"{'Enabled' if enabled else 'Disabled'} global task: {task_name}")
            return True
        except Exception as e:
            logger.error(f"Error setting global task {task_name}: {e}")
            return False
    
    # ============================================================================
    # TASK EXECUTION HELPERS
    # ============================================================================
    
    def should_fetch_log_source(self, log_source_id: str) -> Tuple[bool, Optional[str]]:
        """Check if a log source should be fetched"""
        config = self.get_log_source_config(log_source_id)
        
        if not config.fetch_enabled:
            return False, "Log source fetch is disabled"
        
        # Additional checks can be added here (rate limiting, etc.)
        return True, None
    
    def should_generate_rca_for_service(self, service_id: str) -> Tuple[bool, Optional[str]]:
        """Check if RCA should be generated for a service"""
        config = self.get_service_config(service_id)
        
        if not config.rca_enabled:
            return False, "RCA generation is disabled for this service"
        
        return True, None
    
    def should_index_code_for_service(self, service_id: str) -> Tuple[bool, Optional[str]]:
        """Check if code should be indexed for a service"""
        config = self.get_service_config(service_id)
        
        if not config.index_code_enabled:
            return False, "Code indexing is disabled for this service"
        
        return True, None
    
    def should_cleanup_for_service(self, service_id: str) -> Tuple[bool, Optional[str]]:
        """Check if cleanup should run for a service"""
        config = self.get_service_config(service_id)
        
        if not config.cleanup_enabled:
            return False, "Cleanup is disabled for this service"
        
        return True, None
    
    # ============================================================================
    # UTILITY METHODS
    # ============================================================================
    
    def get_all_enabled_log_sources(self) -> List[str]:
        """Get list of all enabled log source IDs"""
        configs = self.list_log_source_configs()
        return [config.log_source_id for config in configs if config.fetch_enabled]
    
    def get_enabled_log_sources_for_service(self, service_id: str) -> List[str]:
        """Get list of enabled log source IDs for a specific service"""
        configs = self.list_log_source_configs(service_id)
        return [config.log_source_id for config in configs if config.fetch_enabled]
    
    def get_all_enabled_services_for_rca(self) -> List[str]:
        """Get list of all service IDs with RCA enabled"""
        configs = self.list_service_configs()
        return [config.service_id for config in configs if config.rca_enabled]
    
    def delete_log_source_config(self, log_source_id: str) -> bool:
        """Delete configuration for a log source"""
        try:
            key = f"{self.log_source_prefix}{log_source_id}"
            self.redis_client.delete(key)
            logger.info(f"Deleted log source config: {log_source_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting log source config {log_source_id}: {e}")
            return False
    
    def delete_service_config(self, service_id: str) -> bool:
        """Delete configuration for a service"""
        try:
            key = f"{self.service_prefix}{service_id}"
            self.redis_client.delete(key)
            logger.info(f"Deleted service config: {service_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting service config {service_id}: {e}")
            return False

# Global enhanced task config manager instance
enhanced_task_config_manager = EnhancedTaskConfigManager()
