"""
Main log processing pipeline.
Orchestrates parsing, exception extraction, clustering, and RCA.
"""
import logging
from typing import List, Dict, Any
from pathlib import Path
from src.config import settings
from src.ingestion.log_parser import LogParser
from src.services.exception_extractor import ExceptionExtractor
from src.services.clustering import ExceptionClusterer
from src.services.llm_analyzer import LLMAnalyzer
from src.services.gchat_notifier import GChatNotifier

logger = logging.getLogger(__name__)


class LogProcessor:
    """Main log processing orchestrator"""
    
    def __init__(self):
        self.parser = LogParser()
        self.extractor = ExceptionExtractor()
        self.clusterer = ExceptionClusterer()
        self.analyzer = LLMAnalyzer()
        self.gchat_notifier = GChatNotifier()
    
    def process_logs(self, logs: List[Dict[str, Any]], log_source_id: str) -> Dict[str, Any]:
        """
        Process a list of logs end-to-end.
        
        Args:
            logs: List of parsed log entries (dictionaries)
            log_source_id: Required log source ID for strict service association
        
        Returns:
            Processing statistics and results
        """
        logger.info(f"Processing {len(logs)} logs")
        
        stats = {
            'total_logs': 0,
            'error_logs': 0,
            'exceptions_extracted': 0,
            'clusters_created': 0,
            'rca_generated': 0,
            'notifications_sent': 0
        }
        
        # Validate input
        if not logs or not isinstance(logs, list):
            logger.warning("No logs provided or invalid input format")
            return stats
        
        stats['total_logs'] = len(logs)
        
        # Step 1: Filter error logs
        error_logs = [log for log in logs if log.get('level') in settings.log_levels_list]
        stats['error_logs'] = len(error_logs)
        
        logger.info(f"Found {stats['error_logs']} error logs out of {stats['total_logs']} total")
        
        if not error_logs:
            logger.info("No error logs to process")
            return stats
        
        # Step 2: Extract exceptions
        exceptions = []
        for log in error_logs:
            exception_data = self.extractor.extract_exception(log)
            if exception_data:
                # Merge with original log data
                exception_data['log_entry'] = log
                exceptions.append(exception_data)
        
        stats['exceptions_extracted'] = len(exceptions)
        logger.info(f"Extracted {stats['exceptions_extracted']} exceptions")
        
        if not exceptions:
            logger.info("No exceptions to process")
            return stats
        
        # Step 3: Cluster exceptions
        clusters = self.clusterer.cluster_exceptions(exceptions, log_source_id)
        stats['clusters_created'] = len(clusters)
        logger.info(f"Created {stats['clusters_created']} clusters")
        
        # Step 4: Send Google Chat notifications for qualifying clusters
        if settings.enable_gchat_notifications:
            for cluster_id, cluster_exceptions in clusters.items():
                cluster_size = len(cluster_exceptions)
                
                # Check if cluster meets notification threshold
                if cluster_size >= settings.gchat_notification_threshold:
                    try:
                        # Get cluster metadata
                        cluster_data = self.clusterer.get_cluster_details(cluster_id)
                        if cluster_data:
                            # Send notification
                            success = self.gchat_notifier.notify_exception_cluster(
                                cluster_id=cluster_id,
                                cluster_data=cluster_data,
                                exceptions=cluster_exceptions
                            )
                            if success:
                                stats['notifications_sent'] += 1
                                logger.info(f"Sent GChat notification for cluster: {cluster_id}")
                    except Exception as e:
                        logger.error(f"Error sending GChat notification for {cluster_id}: {e}")
        
        # Step 5: Generate RCA for qualifying clusters
        if settings.enable_llm_analysis:
            for cluster_id in clusters.keys():
                if self.clusterer.should_trigger_rca(cluster_id):
                    try:
                        rca_id = self.analyzer.analyze_cluster(cluster_id)
                        if rca_id:
                            stats['rca_generated'] += 1
                            logger.info(f"Generated RCA for cluster: {cluster_id}")
                            
                            # Send RCA completion notification
                            if settings.enable_gchat_notifications:
                                self.gchat_notifier.notify_rca_generated(cluster_id)
                    except Exception as e:
                        logger.error(f"Error generating RCA for {cluster_id}: {e}")
        
        logger.info(f"Processing complete: {stats}")
        return stats
    
    def process_log_file(self, file_path: str, log_source_id: str) -> Dict[str, Any]:
        """
        Process a log file end-to-end (convenience method).
        
        Args:
            file_path: Path to log file
            log_source_id: Required log source ID for strict service association
        
        Returns:
            Processing statistics and results
        """
        logger.info(f"Processing log file: {file_path}")
        
        # Parse logs from file
        logs = self.parser.parse_log_file(file_path)
        
        if not logs:
            logger.warning("No logs parsed from file")
            return {
                'total_logs': 0,
                'error_logs': 0,
                'exceptions_extracted': 0,
                'clusters_created': 0,
                'rca_generated': 0,
                'notifications_sent': 0
            }
        
        # Process the parsed logs
        return self.process_logs(logs, log_source_id)
    
    def get_processing_summary(self) -> Dict[str, Any]:
        """Get summary of recent processing"""
        clusters = self.clusterer.list_active_clusters(limit=20)
        
        return {
            'active_clusters': len(clusters),
            'clusters': clusters
        }
