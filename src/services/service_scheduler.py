"""
Service-Aware Task Scheduler

This module handles per-service task scheduling and execution based on 
individual service configurations for log processing, RCA generation, 
and code indexing.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from celery import Celery
from sqlalchemy.orm import Session

from ..storage.database import get_db
from ..storage.models import Service, LogSource
from .tasks import fetch_and_process_logs, generate_rca_for_clusters

logger = logging.getLogger(__name__)


class ServiceScheduler:
    """Manages per-service task scheduling and execution"""
    
    def __init__(self, celery_app: Celery):
        self.celery_app = celery_app
        
    def schedule_service_tasks(self) -> Dict[str, Any]:
        """
        Schedule tasks for all active services based on their individual configurations.
        
        This method:
        1. Fetches all active services
        2. Checks if tasks are due based on service-specific intervals
        3. Schedules tasks for services that are due
        
        Returns:
            Dictionary with scheduling statistics
        """
        stats = {
            'services_processed': 0,
            'log_fetch_tasks_scheduled': 0,
            'rca_tasks_scheduled': 0,
            'errors': []
        }
        
        try:
            with get_db() as db:
                # Get all active services
                services = db.query(Service).filter(Service.is_active == True).all()
                
                for service in services:
                    try:
                        stats['services_processed'] += 1
                        
                        # Schedule log fetch tasks
                        if self._should_fetch_logs(service):
                            self._schedule_log_fetch(service)
                            stats['log_fetch_tasks_scheduled'] += 1
                            
                        # Schedule RCA generation
                        if self._should_generate_rca(service):
                            self._schedule_rca_generation(service)
                            stats['rca_tasks_scheduled'] += 1
                            
                        # Code indexing is now on-demand (triggered by exception detection)
                        # No longer scheduled periodically
                            
                    except Exception as e:
                        error_msg = f"Error scheduling tasks for service {service.id}: {str(e)}"
                        logger.error(error_msg)
                        stats['errors'].append(error_msg)
                        
        except Exception as e:
            error_msg = f"Error in service scheduler: {str(e)}"
            logger.error(error_msg)
            stats['errors'].append(error_msg)
            
        return stats
    
    def _should_fetch_logs(self, service: Service) -> bool:
        """Check if log fetching is due for this service"""
        if not service.is_active:
            return False
            
        # Check if we have any active log sources for this service
        with get_db() as db:
            active_sources = db.query(LogSource).filter(
                LogSource.service_id == service.id,
                LogSource.is_active == True,
                LogSource.fetch_enabled == True
            ).count()
            
            if active_sources == 0:
                return False
        
        # Check if enough time has passed since last fetch
        if service.last_log_fetch is None:
            return True
            
        time_since_last = datetime.utcnow() - service.last_log_fetch
        interval = timedelta(minutes=service.log_fetch_interval_minutes)
        
        return time_since_last >= interval
    
    def _should_generate_rca(self, service: Service) -> bool:
        """Check if RCA generation is due for this service"""
        if not service.is_active or not service.rca_generation_enabled:
            return False
            
        if service.last_rca_generation is None:
            return True
            
        time_since_last = datetime.utcnow() - service.last_rca_generation
        interval = timedelta(minutes=service.rca_generation_interval_minutes)
        
        return time_since_last >= interval
    
    def _schedule_log_fetch(self, service: Service) -> None:
        """Schedule log fetch task for a specific service"""
        logger.info(f"Scheduling log fetch for service: {service.name}")
        
        # Schedule the task with service-specific parameters
        fetch_and_process_logs.delay(service_id=service.id)
        
        # Update last fetch time
        with get_db() as db:
            db.query(Service).filter(Service.id == service.id).update({
                'last_log_fetch': datetime.utcnow()
            })
    
    def _schedule_rca_generation(self, service: Service) -> None:
        """Schedule RCA generation task for a specific service"""
        logger.info(f"Scheduling RCA generation for service: {service.name}")
        
        # Schedule the task with service-specific parameters
        generate_rca_for_clusters.delay(service_id=service.id)
        
        # Update last RCA generation time
        with get_db() as db:
            db.query(Service).filter(Service.id == service.id).update({
                'last_rca_generation': datetime.utcnow()
            })
            db.commit()
    
    def get_service_status(self, service_id: str) -> Dict[str, Any]:
        """Get detailed status for a specific service"""
        with get_db() as db:
            service = db.query(Service).filter(Service.id == service_id).first()
            if not service:
                return {'error': 'Service not found'}
                
            # Get log sources status
            log_sources = db.query(LogSource).filter(
                LogSource.service_id == service_id
            ).all()
            
            return {
                'service_id': service.id,
                'service_name': service.name,
                'is_active': service.is_active,
                'last_log_fetch': service.last_log_fetch.isoformat() if service.last_log_fetch else None,
                'last_rca_generation': service.last_rca_generation.isoformat() if service.last_rca_generation else None,
                'last_code_indexing': service.last_code_indexing.isoformat() if service.last_code_indexing else None,
                'log_sources_count': len(log_sources),
                'active_log_sources': len([ls for ls in log_sources if ls.is_active and ls.fetch_enabled]),
                'configuration': {
                    'log_fetch_interval_minutes': service.log_fetch_interval_minutes,
                    'rca_generation_enabled': service.rca_generation_enabled,
                    'rca_generation_interval_minutes': service.rca_generation_interval_minutes,
                    'code_indexing_enabled': service.code_indexing_enabled,
                    'code_indexing_interval_hours': service.code_indexing_interval_hours,
                    'git_branch': service.git_branch,
                    'repository_url': service.repository_url
                }
            }
    
    def get_all_services_status(self) -> List[Dict[str, Any]]:
        """Get status for all services"""
        with get_db() as db:
            services = db.query(Service).all()
            return [self.get_service_status(service.id) for service in services]


# Global scheduler instance
service_scheduler = None

def get_service_scheduler(celery_app: Celery) -> ServiceScheduler:
    """Get or create the global service scheduler instance"""
    global service_scheduler
    if service_scheduler is None:
        service_scheduler = ServiceScheduler(celery_app)
    return service_scheduler
