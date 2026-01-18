"""
Task Configuration Management

This module provides a simple way to enable/disable periodic tasks
and manage their configuration at runtime via APIs.
"""
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import redis

from src.config import settings

logger = logging.getLogger(__name__)


class TaskConfigManager:
    """
    Manages configuration for periodic Celery tasks.
    
    Stores task configurations in Redis for persistence and real-time updates.
    """
    
    REDIS_KEY_PREFIX = "luffy:task_config:"
    
    # Default task configurations
    DEFAULT_CONFIGS = {
        "fetch_and_process_logs": {
            "enabled": True,
            "interval_minutes": 30,
            "description": "Fetch and process logs from OpenSearch",
            "last_modified": None,
            "modified_by": None
        },
        "generate_rca_for_clusters": {
            "enabled": True,
            "interval_minutes": 15,
            "description": "Generate RCA for qualifying clusters",
            "last_modified": None,
            "modified_by": None
        },
        "index_code_repository": {
            "enabled": True,
            "cron": "0 2 * * *",  # Daily at 2 AM
            "description": "Index code repository for semantic search",
            "last_modified": None,
            "modified_by": None
        },
        "cleanup_old_data": {
            "enabled": True,
            "cron": "0 3 * * 0",  # Weekly on Sunday at 3 AM
            "description": "Clean up old data from databases",
            "last_modified": None,
            "modified_by": None
        }
    }
    
    def __init__(self):
        """Initialize Redis connection for task config storage"""
        try:
            self.redis_client = redis.from_url(
                settings.redis_url,
                decode_responses=True
            )
            self._initialize_configs()
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis_client = None
    
    def _initialize_configs(self):
        """Initialize default configs if they don't exist"""
        if not self.redis_client:
            return
            
        for task_name, config in self.DEFAULT_CONFIGS.items():
            key = f"{self.REDIS_KEY_PREFIX}{task_name}"
            if not self.redis_client.exists(key):
                self.redis_client.set(key, json.dumps(config))
                logger.info(f"Initialized config for task: {task_name}")
    
    def get_task_config(self, task_name: str) -> Optional[Dict[str, Any]]:
        """
        Get configuration for a specific task.
        
        Args:
            task_name: Name of the task
            
        Returns:
            Task configuration dict or None if not found
        """
        if not self.redis_client:
            # Fallback to default config
            return self.DEFAULT_CONFIGS.get(task_name)
        
        try:
            key = f"{self.REDIS_KEY_PREFIX}{task_name}"
            config_json = self.redis_client.get(key)
            
            if config_json:
                return json.loads(config_json)
            else:
                return self.DEFAULT_CONFIGS.get(task_name)
                
        except Exception as e:
            logger.error(f"Error getting config for {task_name}: {e}")
            return self.DEFAULT_CONFIGS.get(task_name)
    
    def get_all_task_configs(self) -> Dict[str, Dict[str, Any]]:
        """
        Get configurations for all tasks.
        
        Returns:
            Dictionary mapping task names to their configurations
        """
        configs = {}
        
        for task_name in self.DEFAULT_CONFIGS.keys():
            config = self.get_task_config(task_name)
            if config:
                configs[task_name] = config
        
        return configs
    
    def update_task_config(
        self,
        task_name: str,
        enabled: Optional[bool] = None,
        interval_minutes: Optional[int] = None,
        cron: Optional[str] = None,
        modified_by: str = "api"
    ) -> bool:
        """
        Update configuration for a specific task.
        
        Args:
            task_name: Name of the task
            enabled: Whether the task is enabled
            interval_minutes: Interval in minutes (for interval-based tasks)
            cron: Cron expression (for cron-based tasks)
            modified_by: Who/what modified the config
            
        Returns:
            True if successful, False otherwise
        """
        if not self.redis_client:
            logger.error("Redis not available, cannot update config")
            return False
        
        if task_name not in self.DEFAULT_CONFIGS:
            logger.error(f"Unknown task: {task_name}")
            return False
        
        try:
            # Get current config
            current_config = self.get_task_config(task_name)
            
            # Update fields
            if enabled is not None:
                current_config["enabled"] = enabled
            if interval_minutes is not None:
                current_config["interval_minutes"] = interval_minutes
            if cron is not None:
                current_config["cron"] = cron
            
            # Add metadata
            current_config["last_modified"] = datetime.utcnow().isoformat()
            current_config["modified_by"] = modified_by
            
            # Save to Redis
            key = f"{self.REDIS_KEY_PREFIX}{task_name}"
            self.redis_client.set(key, json.dumps(current_config))
            
            logger.info(f"Updated config for task: {task_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating config for {task_name}: {e}")
            return False
    
    def is_task_enabled(self, task_name: str) -> bool:
        """
        Check if a task is enabled.
        
        Args:
            task_name: Name of the task
            
        Returns:
            True if enabled, False otherwise
        """
        config = self.get_task_config(task_name)
        return config.get("enabled", False) if config else False
    
    def enable_task(self, task_name: str, modified_by: str = "api") -> bool:
        """Enable a task"""
        return self.update_task_config(task_name, enabled=True, modified_by=modified_by)
    
    def disable_task(self, task_name: str, modified_by: str = "api") -> bool:
        """Disable a task"""
        return self.update_task_config(task_name, enabled=False, modified_by=modified_by)
    
    def reset_task_config(self, task_name: str) -> bool:
        """Reset a task to its default configuration"""
        if task_name not in self.DEFAULT_CONFIGS:
            return False
        
        if not self.redis_client:
            return False
        
        try:
            key = f"{self.REDIS_KEY_PREFIX}{task_name}"
            self.redis_client.set(key, json.dumps(self.DEFAULT_CONFIGS[task_name]))
            logger.info(f"Reset config for task: {task_name}")
            return True
        except Exception as e:
            logger.error(f"Error resetting config for {task_name}: {e}")
            return False


# Global instance
task_config_manager = TaskConfigManager()
