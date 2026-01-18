"""
Statistics service for dashboard metrics and trends.
Provides real-time data for exception trends, service statistics, and system health.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict
import logging
from sqlalchemy import func, and_
from src.storage.database import get_db
from src.storage.models import ExceptionCluster, Service, RCAResult, LogSource

logger = logging.getLogger(__name__)


class StatsService:
    """Service for generating dashboard statistics and trends"""
    
    def _parse_time_filter(self, time_filter: Optional[str]) -> Optional[datetime]:
        """Parse time filter string to datetime cutoff"""
        if not time_filter:
            return None
            
        now = datetime.utcnow()
        
        if time_filter == '5m':
            return now - timedelta(minutes=5)
        elif time_filter == '10m':
            return now - timedelta(minutes=10)
        elif time_filter == '30m':
            return now - timedelta(minutes=30)
        elif time_filter == '1h':
            return now - timedelta(hours=1)
        elif time_filter == '6h':
            return now - timedelta(hours=6)
        elif time_filter == '24h':
            return now - timedelta(hours=24)
        elif time_filter == '7d':
            return now - timedelta(days=7)
        elif time_filter == '30d':
            return now - timedelta(days=30)
        else:
            return None
    
    def get_dashboard_stats(self, service_id: Optional[str] = None, time_filter: Optional[str] = None) -> Dict[str, Any]:
        """
        Get dashboard statistics (active exceptions only), optionally filtered by service and time.
        
        Args:
            service_id: Optional service ID to filter statistics
            time_filter: Optional time filter (5m, 10m, 30m, 1h, 6h, 24h, 7d, 30d)
        
        Returns:
            Dictionary with stats (system-wide or service-specific)
        """
        with get_db() as db:
            # Parse time filter
            time_cutoff = self._parse_time_filter(time_filter)
            
            # Build base query for active clusters
            base_query = db.query(ExceptionCluster).filter(
                ExceptionCluster.status == 'active'
            )
            
            # Add service filter if provided
            if service_id:
                base_query = base_query.filter(
                    ExceptionCluster.service_id == service_id
                )
            
            # Add time filter if provided
            if time_cutoff:
                base_query = base_query.filter(
                    ExceptionCluster.last_seen >= time_cutoff
                )
            
            active_clusters = base_query.count()
            
            # Build RCA query with service filter
            rca_query = db.query(RCAResult).join(ExceptionCluster).filter(
                ExceptionCluster.status == 'active'
            )
            if service_id:
                rca_query = rca_query.filter(
                    ExceptionCluster.service_id == service_id
                )
            if time_cutoff:
                rca_query = rca_query.filter(
                    ExceptionCluster.last_seen >= time_cutoff
                )
            rca_generated = rca_query.count()
            
            # Calculate trends (last 7 days vs previous 7 days)
            now = datetime.utcnow()
            seven_days_ago = now - timedelta(days=7)
            fourteen_days_ago = now - timedelta(days=14)
            
            # Build recent clusters query with service filter
            recent_query = db.query(ExceptionCluster).filter(
                and_(
                    ExceptionCluster.first_seen >= seven_days_ago,
                    ExceptionCluster.status == 'active'
                )
            )
            if service_id:
                recent_query = recent_query.filter(
                    ExceptionCluster.service_id == service_id
                )
            recent_clusters = recent_query.count()
            
            # Build previous clusters query with service filter
            previous_query = db.query(ExceptionCluster).filter(
                and_(
                    ExceptionCluster.first_seen >= fourteen_days_ago,
                    ExceptionCluster.first_seen < seven_days_ago,
                    ExceptionCluster.status == 'active'
                )
            )
            if service_id:
                previous_query = previous_query.filter(
                    ExceptionCluster.service_id == service_id
                )
            previous_clusters = previous_query.count()
            
            # Calculate percentage change
            clusters_change = 0
            if previous_clusters > 0:
                clusters_change = ((recent_clusters - previous_clusters) / previous_clusters) * 100
            
            # Build recent RCA query with service filter
            recent_rca_query = db.query(RCAResult).join(ExceptionCluster).filter(
                and_(
                    RCAResult.created_at >= seven_days_ago,
                    ExceptionCluster.status == 'active'
                )
            )
            if service_id:
                recent_rca_query = recent_rca_query.filter(
                    ExceptionCluster.service_id == service_id
                )
            recent_rca = recent_rca_query.count()
            
            # Build previous RCA query with service filter
            previous_rca_query = db.query(RCAResult).join(ExceptionCluster).filter(
                and_(
                    RCAResult.created_at >= fourteen_days_ago,
                    RCAResult.created_at < seven_days_ago,
                    ExceptionCluster.status == 'active'
                )
            )
            if service_id:
                previous_rca_query = previous_rca_query.filter(
                    ExceptionCluster.service_id == service_id
                )
            previous_rca = previous_rca_query.count()
            
            rca_change = 0
            if previous_rca > 0:
                rca_change = ((recent_rca - previous_rca) / previous_rca) * 100
            
            # System health calculation
            system_health = 'healthy'
            if active_clusters > 50:
                system_health = 'degraded'
            if active_clusters > 100:
                system_health = 'down'
            
            # Build logs processed query with service filter
            logs_query = db.query(func.sum(ExceptionCluster.cluster_size)).filter(
                ExceptionCluster.status == 'active'
            )
            if service_id:
                logs_query = logs_query.filter(
                    ExceptionCluster.service_id == service_id
                )
            if time_cutoff:
                logs_query = logs_query.filter(
                    ExceptionCluster.last_seen >= time_cutoff
                )
            logs_processed = logs_query.scalar() or 0
            
            return {
                'total_clusters': active_clusters,  # Only active clusters
                'active_exceptions': active_clusters,  # Same as total_clusters
                'rca_generated': rca_generated,
                'system_health': system_health,
                'logs_processed': int(logs_processed),
                'trends': {
                    'clusters_change': round(clusters_change, 1),
                    'rca_change': round(rca_change, 1)
                }
            }
    
    def get_exception_trends(self, days: int = 7, service_id: Optional[str] = None, log_source_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get exception trends over time (active exceptions only).
        
        Args:
            days: Number of days to include (max 30)
            service_id: Optional service filter
            log_source_id: Optional log source filter
            
        Returns:
            List of daily exception counts (always returns data for all days, even if zero)
        """
        if days > 30:
            days = 30
        if days < 1:
            days = 1
            
        with get_db() as db:
            now = datetime.utcnow()
            start_date = now - timedelta(days=days)
            
            # Build query filters for active clusters only
            query_filters = [
                ExceptionCluster.last_seen >= start_date,
                ExceptionCluster.status == 'active'
            ]
            
            if service_id:
                query_filters.append(ExceptionCluster.service_id == service_id)
            if log_source_id:
                query_filters.append(ExceptionCluster.log_source_id == log_source_id)
            
            # Get all active clusters within the date range
            clusters = db.query(ExceptionCluster).filter(
                and_(*query_filters)
            ).all()
            
            # Group by date (using last_seen for activity)
            daily_counts = defaultdict(int)
            
            for cluster in clusters:
                # Count exceptions by last_seen date (when they were last active)
                date_key = cluster.last_seen.strftime('%Y-%m-%d')
                # Use cluster_size to count actual exception occurrences
                daily_counts[date_key] += cluster.cluster_size or 1
            
            # Create result list for all days in range (ensures graph always shows all days)
            result = []
            current_date = start_date
            
            while current_date <= now:
                date_key = current_date.strftime('%Y-%m-%d')
                date_label = current_date.strftime('%b %d')
                
                result.append({
                    'date': date_label,
                    'full_date': date_key,
                    'exceptions': daily_counts.get(date_key, 0)  # Returns 0 if no exceptions
                })
                
                current_date += timedelta(days=1)
            
            logger.info(f"Generated trend data for {days} days: {len(result)} data points, total exceptions: {sum(d['exceptions'] for d in result)}")
            return result
    
    def get_exceptions_by_service(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get exception counts grouped by service.
        
        Args:
            limit: Maximum number of services to return
            
        Returns:
            List of services with exception counts
        """
        with get_db() as db:
            # Get exception counts by service
            service_stats = db.query(
                ExceptionCluster.service_id,
                func.count(ExceptionCluster.cluster_id).label('count'),
                func.sum(ExceptionCluster.cluster_size).label('total_exceptions')
            ).filter(
                ExceptionCluster.status == 'active'  # Only active exceptions
            ).group_by(
                ExceptionCluster.service_id
            ).order_by(
                func.count(ExceptionCluster.cluster_id).desc()
            ).limit(limit).all()
            
            result = []
            for service_id, cluster_count, total_exceptions in service_stats:
                # Get service name
                service = db.query(Service).filter_by(id=service_id).first()
                service_name = service.name if service else service_id
                
                result.append({
                    'service': service_name,
                    'count': int(total_exceptions) if total_exceptions else cluster_count,
                    'clusters': cluster_count
                })
            
            logger.info(f"Generated service stats for {len(result)} services")
            return result
    
    def get_severity_distribution(self) -> List[Dict[str, Any]]:
        """
        Get distribution of exceptions by severity.
        
        Returns:
            List of severity counts
        """
        with get_db() as db:
            severity_stats = db.query(
                ExceptionCluster.severity,
                func.count(ExceptionCluster.cluster_id).label('count')
            ).filter(
                ExceptionCluster.status == 'active'
            ).group_by(
                ExceptionCluster.severity
            ).all()
            
            result = []
            for severity, count in severity_stats:
                result.append({
                    'severity': severity or 'unknown',
                    'count': count
                })
            
            return result


# Global stats service instance
stats_service = StatsService()
