"""
Google Chat notification service.
Sends formatted notifications about exceptions and clusters to Google Chat.
"""
import json
import logging
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime
from src.config import settings

logger = logging.getLogger(__name__)


class GChatNotifier:
    """Send notifications to Google Chat via webhooks"""
    
    def __init__(self, webhook_url: str = None):
        """
        Initialize GChat notifier.
        
        Args:
            webhook_url: Google Chat webhook URL (defaults to settings)
        """
        self.webhook_url = webhook_url or settings.gchat_webhook_url
        self.enabled = settings.enable_gchat_notifications and bool(self.webhook_url)
        
        if not self.enabled:
            logger.info("Google Chat notifications are disabled")
        elif not self.webhook_url:
            logger.warning("Google Chat webhook URL not configured")
    
    def send_notification(self, message: Dict[str, Any]) -> bool:
        """
        Send a notification to Google Chat.
        
        Args:
            message: Google Chat message in Card format
        
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            logger.debug("Notifications disabled, skipping send")
            return False
        
        try:
            response = requests.post(
                self.webhook_url,
                json=message,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            response.raise_for_status()
            logger.info("Successfully sent Google Chat notification")
            return True
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Google Chat notification: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending notification: {e}")
            return False
    
    def notify_exception_cluster(
        self,
        cluster_id: str,
        cluster_data: Dict[str, Any],
        exceptions: List[Dict[str, Any]] = None
    ) -> bool:
        """
        Send notification about an exception cluster.
        
        Args:
            cluster_id: Cluster identifier
            cluster_data: Cluster metadata
            exceptions: List of exceptions in cluster (optional)
        
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        # Extract key information
        exception_type = cluster_data.get('exception_type', 'Unknown')
        exception_message = cluster_data.get('exception_message', 'No message')
        cluster_size = cluster_data.get('cluster_size', len(exceptions) if exceptions else 0)
        service_id = cluster_data.get('service_id', 'Unknown')
        frequency_24h = cluster_data.get('frequency_24h', cluster_size)
        
        # Truncate message if too long
        if len(exception_message) > 200:
            exception_message = exception_message[:200] + "..."
        
        # Build Google Chat card message
        message = {
            "cards": [
                {
                    "header": {
                        "title": f"🚨 Exception Alert: {exception_type}",
                        "subtitle": f"Cluster: {cluster_id}",
                        "imageUrl": "https://fonts.gstatic.com/s/i/productlogos/chat/v1/web-96dp/logo_chat_color_1x_web_96dp.png"
                    },
                    "sections": [
                        {
                            "widgets": [
                                {
                                    "keyValue": {
                                        "topLabel": "Service",
                                        "content": service_id,
                                        "contentMultiline": False,
                                        "icon": "BOOKMARK"
                                    }
                                },
                                {
                                    "keyValue": {
                                        "topLabel": "Exception Type",
                                        "content": exception_type,
                                        "contentMultiline": False,
                                        "icon": "DESCRIPTION"
                                    }
                                },
                                {
                                    "keyValue": {
                                        "topLabel": "Cluster Size",
                                        "content": str(cluster_size),
                                        "contentMultiline": False,
                                        "icon": "MULTIPLE_PEOPLE"
                                    }
                                },
                                {
                                    "keyValue": {
                                        "topLabel": "Frequency (24h)",
                                        "content": str(frequency_24h),
                                        "contentMultiline": False,
                                        "icon": "CLOCK"
                                    }
                                }
                            ]
                        },
                        {
                            "widgets": [
                                {
                                    "textParagraph": {
                                        "text": f"<b>Message:</b><br>{exception_message}"
                                    }
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        # Add stack trace info if available
        if exceptions and len(exceptions) > 0:
            first_exception = exceptions[0]
            stack_frames = first_exception.get('stack_frames', [])
            
            if stack_frames:
                top_frame = stack_frames[0]
                frame_text = f"<font color=\"#666666\">at {top_frame.get('symbol', 'unknown')} ({top_frame.get('file', 'unknown')}:{top_frame.get('line', '?')})</font>"
                
                message["cards"][0]["sections"].append({
                    "widgets": [
                        {
                            "textParagraph": {
                                "text": f"<b>Top Stack Frame:</b><br>{frame_text}"
                            }
                        }
                    ]
                })
        
        # Add timestamp
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message["cards"][0]["sections"].append({
            "widgets": [
                {
                    "textParagraph": {
                        "text": f"<font color=\"#999999\"><i>Detected at: {current_time}</i></font>"
                    }
                }
            ]
        })
        
        return self.send_notification(message)
    
    def notify_simple(self, title: str, message: str, severity: str = "INFO") -> bool:
        """
        Send a simple text notification.
        
        Args:
            title: Notification title
            message: Notification message
            severity: Severity level (INFO, WARNING, ERROR)
        
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        # Choose icon based on severity
        icon_map = {
            "INFO": "ℹ️",
            "WARNING": "⚠️",
            "ERROR": "🔴",
            "CRITICAL": "🚨"
        }
        icon = icon_map.get(severity.upper(), "📢")
        
        gchat_message = {
            "text": f"{icon} *{title}*\n{message}"
        }
        
        return self.send_notification(gchat_message)
    
    def notify_rca_generated(self, cluster_id: str, rca_summary: str = None) -> bool:
        """
        Send notification that RCA was generated for a cluster.
        
        Args:
            cluster_id: Cluster identifier
            rca_summary: Summary of RCA (optional)
        
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        message_text = f"✅ *RCA Generated*\nCluster: {cluster_id}"
        if rca_summary:
            message_text += f"\n\n{rca_summary[:300]}"
        
        gchat_message = {
            "text": message_text
        }
        
        return self.send_notification(gchat_message)
    
    def test_connection(self) -> bool:
        """
        Test the Google Chat webhook connection.
        
        Returns:
            True if connection is successful, False otherwise
        """
        if not self.webhook_url:
            logger.error("No webhook URL configured")
            return False
        
        test_message = {
            "text": "🔔 Test notification from Luffy Log Observability Platform"
        }
        
        return self.send_notification(test_message)


# Convenience function
def send_exception_alert(
    cluster_id: str,
    cluster_data: Dict[str, Any],
    exceptions: List[Dict[str, Any]] = None
) -> bool:
    """
    Convenience function to send exception alert.
    
    Args:
        cluster_id: Cluster identifier
        cluster_data: Cluster metadata
        exceptions: List of exceptions in cluster
    
    Returns:
        True if successful, False otherwise
    """
    notifier = GChatNotifier()
    return notifier.notify_exception_cluster(cluster_id, cluster_data, exceptions)
