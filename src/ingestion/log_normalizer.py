"""
Shared log normalization module for consistent log format across all sources.

This module normalizes logs from OpenSearch and file sources to a unified format.
OpenSearch logs often have raw log content in a 'log' field that needs parsing.
"""
import re
import hashlib
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class LogNormalizer:
    """
    Normalize logs from various sources to a consistent format.
    
    Handles:
    - OpenSearch logs with raw content in 'log' field
    - File-parsed logs with structured fields
    - Field name variations (@timestamp vs timestamp, log_level vs level)
    """
    
    def __init__(self):
        # Regex pattern for parsing log lines
        # Matches: 2025-11-08T15:04:03.709 [thread] LEVEL logger.name - message
        self.log_pattern = re.compile(
            r'^(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3})\s+'
            r'\[(?P<thread>[^\]]+)\]\s+'
            r'(?P<level>\w+)\s+'
            r'(?P<logger>\S+)\s+-\s+'
            r'(?P<message>.*)$'
        )
        
        # Pattern to detect stack traces
        self.stack_trace_pattern = re.compile(r'^\s+(at\s|Caused by:|\.{3}\s+\d+\s+more)')
    
    def normalize_logs(self, logs: List[Dict[str, Any]], source: str = 'unknown') -> List[Dict[str, Any]]:
        """
        Normalize a list of logs from any source.
        
        Args:
            logs: List of log entries
            source: Source identifier ('opensearch', 'file', etc.)
            
        Returns:
            List of normalized log entries
        """
        normalized = []
        
        for log in logs:
            try:
                normalized_log = self.normalize_log(log, source)
                if normalized_log:
                    normalized.append(normalized_log)
            except Exception as e:
                logger.error(f"Error normalizing log: {e}")
                continue
        
        logger.info(f"Normalized {len(normalized)}/{len(logs)} logs from source: {source}")
        return normalized
    
    def normalize_log(self, log: Dict[str, Any], source: str = 'unknown') -> Optional[Dict[str, Any]]:
        """
        Normalize a single log entry.
        
        Args:
            log: Log entry to normalize
            source: Source identifier
            
        Returns:
            Normalized log entry with consistent structure
        """
        if not log:
            return None
        
        # Start with a copy of the original log
        normalized = dict(log)
        
        # Check if this is an OpenSearch log with 'log' field containing raw content
        if 'log' in normalized and isinstance(normalized['log'], str):
            # Parse the raw log content
            parsed = self._parse_log_line(normalized['log'])
            if parsed:
                # Merge parsed data with existing fields (parsed data takes precedence for structure)
                normalized.update(parsed)
        
        # Ensure required fields exist
        normalized = self._ensure_log_id(normalized)
        normalized = self._normalize_timestamp(normalized)
        normalized = self._normalize_level(normalized)
        normalized = self._normalize_message(normalized)
        normalized = self._normalize_logger(normalized)
        normalized = self._normalize_thread(normalized)
        normalized = self._normalize_service(normalized)
        normalized = self._normalize_stack_trace(normalized)
        
        # Add source metadata
        if 'source' not in normalized:
            normalized['source'] = source
        
        # Clean up OpenSearch-specific fields after parsing
        # Remove redundant fields that were only needed for parsing
        if source == 'opensearch':
            # Remove the raw 'log' field after parsing (we've extracted all data from it)
            if 'log' in normalized:
                del normalized['log']
            
            # Remove @timestamp if we have timestamp (they're duplicates after normalization)
            if '@timestamp' in normalized and 'timestamp' in normalized:
                del normalized['@timestamp']
            
            # Remove log_level if we have level (they're duplicates after normalization)
            if 'log_level' in normalized and 'level' in normalized:
                del normalized['log_level']
        
        return normalized
    
    def _parse_log_line(self, log_line: str) -> Optional[Dict[str, Any]]:
        """
        Parse a raw log line into structured fields.
        
        Handles multi-line logs by parsing only the first line for structured fields,
        and extracting stack trace from remaining lines.
        
        Args:
            log_line: Raw log line string (may be multi-line)
            
        Returns:
            Parsed log fields or None if parsing fails
        """
        # Split into lines for multi-line logs (e.g., with stack traces)
        lines = log_line.split('\n')
        first_line = lines[0].strip()
        
        # Try to match the log pattern on the first line
        match = self.log_pattern.match(first_line)
        if not match:
            # If pattern doesn't match, return None (will use existing fields)
            return None
        
        parsed = match.groupdict()
        
        # Clean up fields
        parsed['level'] = parsed['level'].strip().upper()
        parsed['message'] = parsed['message'].strip()
        parsed['thread'] = parsed['thread'].strip()
        parsed['logger'] = parsed['logger'].strip()
        
        # If there are additional lines, they might be a stack trace
        if len(lines) > 1:
            remaining_lines = [line for line in lines[1:] if line.strip()]
            if remaining_lines:
                # Check if it looks like a stack trace
                if any(self.stack_trace_pattern.match(line) for line in remaining_lines[:3]):
                    # It's a stack trace - include it
                    parsed['stack_trace'] = remaining_lines
                else:
                    # Not a stack trace - append to message
                    parsed['message'] = parsed['message'] + '\n' + '\n'.join(remaining_lines)
        
        return parsed
    
    def _ensure_log_id(self, log: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure log has a unique ID"""
        if 'log_id' not in log or not log['log_id']:
            # Generate ID from timestamp + logger + thread + message
            unique_str = (
                f"{log.get('timestamp', '')}_"
                f"{log.get('logger', '')}_"
                f"{log.get('thread', '')}_"
                f"{log.get('message', '')[:50]}"
            )
            log['log_id'] = hashlib.md5(unique_str.encode()).hexdigest()
        
        return log
    
    def _normalize_timestamp(self, log: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize timestamp field"""
        # Check various timestamp field names
        timestamp = (
            log.get('timestamp') or 
            log.get('@timestamp') or 
            log.get('time') or
            log.get('datetime')
        )
        
        if timestamp:
            log['timestamp'] = str(timestamp)
        else:
            # Use current time as fallback
            log['timestamp'] = datetime.utcnow().isoformat()
        
        return log
    
    def _normalize_level(self, log: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize log level field"""
        level = (
            log.get('level') or 
            log.get('log_level') or 
            log.get('severity') or
            'INFO'
        )
        
        # Normalize to uppercase
        log['level'] = str(level).strip().upper()
        
        # Map common variations
        level_mapping = {
            'WARN': 'WARNING',
            'ERR': 'ERROR',
            'FATAL': 'CRITICAL',
            'SEVERE': 'CRITICAL',
            'TRACE': 'DEBUG',
        }
        
        log['level'] = level_mapping.get(log['level'], log['level'])
        
        return log
    
    def _normalize_message(self, log: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize message field"""
        message = (
            log.get('message') or 
            log.get('msg') or 
            log.get('text') or
            log.get('log_message') or
            ''
        )
        
        log['message'] = str(message).strip()
        
        return log
    
    def _normalize_logger(self, log: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize logger field"""
        logger_name = (
            log.get('logger') or 
            log.get('logger_name') or 
            log.get('class') or
            log.get('category') or
            'unknown'
        )
        
        log['logger'] = str(logger_name).strip()
        
        return log
    
    def _normalize_thread(self, log: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize thread field"""
        thread = (
            log.get('thread') or 
            log.get('thread_name') or 
            log.get('thread_id') or
            'main'
        )
        
        log['thread'] = str(thread).strip()
        
        return log
    
    def _normalize_service(self, log: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize service field"""
        service = (
            log.get('service') or 
            log.get('application') or 
            log.get('app_name') or
            log.get('service_name') or
            'unknown'
        )
        
        log['service'] = str(service).strip()
        
        return log
    
    def _normalize_stack_trace(self, log: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize stack trace field"""
        # Check if stack_trace exists and is a list
        if 'stack_trace' in log:
            if isinstance(log['stack_trace'], list):
                # Already in correct format
                pass
            elif isinstance(log['stack_trace'], str):
                # Convert string to list of lines
                log['stack_trace'] = log['stack_trace'].split('\n')
            else:
                # Remove invalid stack_trace
                del log['stack_trace']
        
        # Check for exception field (common in OpenSearch)
        elif 'exception' in log:
            exception = log['exception']
            if isinstance(exception, str):
                log['stack_trace'] = exception.split('\n')
            elif isinstance(exception, dict):
                # Extract stack trace from exception object
                stack = exception.get('stacktrace') or exception.get('stack_trace')
                if stack:
                    if isinstance(stack, str):
                        log['stack_trace'] = stack.split('\n')
                    elif isinstance(stack, list):
                        log['stack_trace'] = stack
        
        # Check for error field
        elif 'error' in log:
            error = log['error']
            if isinstance(error, str) and '\n' in error:
                log['stack_trace'] = error.split('\n')
        
        return log


# Convenience function
def normalize_logs(logs: List[Dict[str, Any]], source: str = 'unknown') -> List[Dict[str, Any]]:
    """
    Normalize a list of logs from any source.
    
    Args:
        logs: List of log entries
        source: Source identifier ('opensearch', 'file', etc.)
        
    Returns:
        List of normalized log entries
    """
    normalizer = LogNormalizer()
    return normalizer.normalize_logs(logs, source)
