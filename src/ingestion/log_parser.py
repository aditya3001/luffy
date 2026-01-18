"""
Enhanced log parser with normalization and structure extraction.
Inspired by LogAI patterns for production log analysis.
"""
import re
import json
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from src.ingestion.log_normalizer import LogNormalizer

logger = logging.getLogger(__name__)


class LogParser:
    """Parse and normalize logs from various formats"""
    
    def __init__(self):
        # Regex pattern for logs matching: 
        # %date{"yyyy-MM-dd'T'HH:mm:ss.SSS", UTC} [%thread] %-5level %logger{36} - %msg%n
        # Example: 2023-10-15T14:30:45.123 [main] INFO  com.example.MyClass - Application started
        self.log_pattern = re.compile(
            r'^(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3})\s+'
            r'\[(?P<thread>[^\]]+)\]\s+'
            r'(?P<level>\w+)\s+'
            r'(?P<logger>\S+)\s+-\s+'
            r'(?P<message>.*)$'
        )
        
        # Pattern to detect stack traces (lines starting with "at " or "Caused by:")
        self.stack_trace_pattern = re.compile(r'^\s+(at\s|Caused by:|\.{3}\s+\d+\s+more)')
        
        # Current multi-line log being assembled
        self._current_log = None
        
        # Log normalizer for consistent output format
        self.normalizer = LogNormalizer()
    
    def parse_log_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Parse a log file and return structured log entries.
        
        Args:
            file_path: Path to the log file
        
        Returns:
            List of parsed log entries
        """
        parsed_logs = []
        
        try:
            with open(file_path, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.rstrip('\n')
                    if not line:
                        continue
                    
                    # Check if this is a new log entry or continuation of previous
                    parsed = self.parse_line(line)
                    if parsed:
                        # If we have a previous log being assembled, save it
                        if self._current_log:
                            self._current_log['_line_end'] = line_num - 1
                            parsed_logs.append(self._current_log)
                        
                        # Start new log entry
                        parsed['_line_number'] = line_num
                        self._current_log = parsed
                    else:
                        # This is a continuation line (likely stack trace or multi-line message)
                        if self._current_log:
                            if 'stack_trace' not in self._current_log:
                                self._current_log['stack_trace'] = []
                            self._current_log['stack_trace'].append(line)
                            # Also append to message for full context
                            self._current_log['message'] += '\n' + line
                        else:
                            logger.warning(f"Orphaned continuation line {line_num}: {line[:100]}")
                
                # Don't forget the last log entry
                if self._current_log:
                    self._current_log['_line_end'] = line_num
                    parsed_logs.append(self._current_log)
                    self._current_log = None
        
        except FileNotFoundError:
            logger.error(f"Log file not found: {file_path}")
        except Exception as e:
            logger.error(f"Error reading log file: {e}")
        
        logger.info(f"Parsed {len(parsed_logs)} log entries from {file_path}")
        
        # Normalize logs to ensure consistent format
        normalized_logs = self.normalizer.normalize_logs(parsed_logs, source='file')
        logger.info(f"Normalized {len(normalized_logs)} logs")
        
        return normalized_logs
    
    def parse_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse a single log line"""
        match = self.log_pattern.match(line)
        if not match:
            return None
        
        log_data = match.groupdict()
        
        # Strip whitespace from level (since it's left-aligned with padding)
        log_data['level'] = log_data['level'].strip()
        log_data['message'] = log_data['message'].strip()
        log_data['thread'] = log_data['thread'].strip()
        log_data['logger'] = log_data['logger'].strip()
        
        # Normalize timestamp
        log_data['timestamp_parsed'] = self._parse_timestamp(log_data['timestamp'])
        
        # Generate log ID
        log_data['log_id'] = self._generate_log_id(log_data)
        
        return log_data
    
    def _parse_timestamp(self, timestamp_str: str) -> Optional[datetime]:
        """Parse timestamp string to datetime object"""
        try:
            # Parse ISO 8601 format with milliseconds: 2023-10-15T14:30:45.123
            # Add UTC timezone since the pattern specifies UTC
            dt = datetime.strptime(timestamp_str, '%Y-%m-%dT%H:%M:%S.%f')
            # Note: datetime.strptime doesn't set timezone, but logs are in UTC
            return dt
        except ValueError as e:
            logger.warning(f"Could not parse timestamp '{timestamp_str}': {e}")
            return None
    
    def _generate_log_id(self, log_data: Dict[str, Any]) -> str:
        """Generate unique ID for log entry"""
        # Use timestamp + thread + logger for uniqueness
        unique_str = (
            f"{log_data.get('timestamp', '')}_"
            f"{log_data.get('thread', '')}_"
            f"{log_data.get('logger', '')}_"
            f"{log_data.get('message', '')[:50]}"  # First 50 chars of message
        )
        return hashlib.md5(unique_str.encode()).hexdigest()


def parse_log_file(file_path: str) -> List[Dict[str, Any]]:
    """
    Legacy function for backward compatibility.
    Parse a log file and return structured log entries.
    """
    parser = LogParser()
    return parser.parse_log_file(file_path)
