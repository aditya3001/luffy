"""
Exception extraction from log entries.
Detects stack traces, parses frames, and extracts exception details.
"""
import re
import hashlib
from typing import List, Dict, Any, Optional
import logging
from src.services.log_normalizer import get_normalizer

logger = logging.getLogger(__name__)


class ExceptionExtractor:
    """Extract and parse exceptions from log entries"""
    
    def __init__(self):
        # Pattern to detect Java/Python stack traces in error field
        self.stack_trace_patterns = [
            # Java: com.company.ClassName.methodName(FileName.java:123)
            re.compile(r'at\s+([\w.$]+)\(([\w.]+):(\d+)\)'),
            # Python: File "/path/to/file.py", line 123, in function_name
            re.compile(r'File\s+"([^"]+)",\s+line\s+(\d+),\s+in\s+(\w+)'),
        ]
        
        # Pattern to detect exception type and message
        self.exception_pattern = re.compile(
            r'([\w.]+(?:Exception|Error)):\s*(.+?)(?=\s+at\s+|\s+File\s+|\n|$)',
            re.MULTILINE | re.DOTALL
        )
    
    def extract_exception(self, log_entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract exception details from a log entry.
        
        Args:
            log_entry: Parsed log entry
        
        Returns:
            Exception details or None if no exception found
        """
        # Check if this is an error log
        if log_entry.get('level') not in ['ERROR', 'CRITICAL', 'FATAL']:
            return None
        
        # print("log_entry : ",log_entry)
        # Get the message and stack trace
        message = log_entry.get('message', '')
        print("message : ",message)
        stack_trace_lines = log_entry.get('stack_trace', [])
        print("stack_trace_lines : ",stack_trace_lines)
        
        # Combine message and stack trace for analysis
        if stack_trace_lines:
            error_text = message + '\n' + '\n'.join(stack_trace_lines)
        else:
            error_text = message
        
        if not error_text:
            return None
        
        # Extract exception type and message
        exception_match = self.exception_pattern.search(error_text)
        if not exception_match:
            # Even if no structured exception, treat as generic error
            exception_type = 'UnknownError'
            exception_message = message[:200]  # Truncate message only
        else:
            exception_type = exception_match.group(1)
            exception_message = exception_match.group(2).strip()
        
        # Extract stack trace frames
        stack_frames = self.extract_stack_frames(error_text)
        # if stack_frames:
        #     print(f"stack frames are : ${stack_frames}")
        
        # Get logger path for fingerprinting
        logger_name = log_entry.get('logger', 'unknown')
        
        # Generate fingerprints based on whether we have stack trace
        if stack_frames:
            # Has stack trace: use traditional fingerprinting
            fingerprint_static = self.generate_static_fingerprint(exception_type, stack_frames, logger_name)
            fingerprint_template = None
            fingerprint_semantic = None
            fingerprint_category = None
        else:
            # No stack trace: use multi-level fingerprinting for better clustering
            normalizer = get_normalizer()
            
            multi_fingerprints = normalizer.generate_multi_level_fingerprints(
                message=exception_message,
                exception_type=exception_type,
                logger_name=logger_name
            )
            
            # Use template fingerprint as primary for logs without stack trace
            fingerprint_static = multi_fingerprints['template']
            fingerprint_template = multi_fingerprints['template']
            fingerprint_semantic = multi_fingerprints['semantic']
            fingerprint_category = multi_fingerprints['category']
            
            # Extract additional metadata for better clustering
            error_category = normalizer.extract_error_category(exception_message)
            key_terms = normalizer.extract_key_terms(exception_message)
            structured_data = normalizer.extract_structured_data(exception_message)
        
        exception_data = {
            'exception_type': exception_type,
            'exception_message': exception_message,
            'stack_frames': stack_frames,
            'fingerprint_static': fingerprint_static,
            'has_stack_trace': len(stack_frames) > 0,
            'top_frame': stack_frames[0] if stack_frames else None,
            # Include original log metadata for context
            'logger': log_entry.get('logger', 'unknown'),
            'thread': log_entry.get('thread', 'unknown'),
            'log_id': log_entry.get('log_id'),
        }
        
        # Add multi-level fingerprints for logs without stack trace
        if not stack_frames:
            exception_data.update({
                'fingerprint_template': fingerprint_template,
                'fingerprint_semantic': fingerprint_semantic,
                'fingerprint_category': fingerprint_category,
                'error_category': error_category,
                'key_terms': key_terms,
                'structured_data': structured_data,
            })
        
        return exception_data
    
    def extract_stack_frames(self, error_text: str) -> List[Dict[str, Any]]:
        """Extract stack trace frames from error text"""
        frames = []
        
        for pattern in self.stack_trace_patterns:
            matches = pattern.findall(error_text)
            # print(f"pattern : ${pattern.pattern}")
            # Java pattern: (class.method, file, line)
            if pattern.pattern.startswith(r'at\s+'):
                print(f"matches : ${matches}")
                for match in matches:
                    full_symbol, file_name, line_num = match
                    frames.append({
                        'symbol': full_symbol,
                        'file': file_name,
                        'line': int(line_num),
                        'frame_type': 'java'
                    })
            
            # Python pattern: (file_path, line, function)
            elif pattern.pattern.startswith(r'File\s+'):
                # print(f"matches : ${matches}")
                for match in matches:
                    file_path, line_num, function_name = match
                    frames.append({
                        'symbol': function_name,
                        'file': file_path,
                        'line': int(line_num),
                        'frame_type': 'python'
                    })
        
        return frames
    
    def generate_static_fingerprint(
        self,
        exception_type: str,
        stack_frames: List[Dict[str, Any]],
        logger_path: Optional[str] = None
    ) -> str:
        """
        Generate static fingerprint based on exception type and stack frames.
        Used for exact matching of similar exceptions.
        
        For exceptions with stack traces: Uses exception type + top 3 frame signatures
        For exceptions without stack traces: Includes logger_path for better clustering
        """
        # Use exception type + top 3 frame signatures
        components = [exception_type]
        
        if stack_frames:
            # Has stack trace: use traditional fingerprinting
            for frame in stack_frames[:3]:
                # Use file + symbol (ignore line numbers for grouping)
                frame_sig = f"{frame.get('file', '')}:{frame.get('symbol', '')}"
                components.append(frame_sig)
        elif logger_path:
            # No stack trace: include logger_path for better clustering
            # This helps group exceptions from the same logger/class together
            components.append(f"logger:{logger_path}")
        
        fingerprint_str = '|'.join(components)
        return hashlib.sha256(fingerprint_str.encode()).hexdigest()[:16]
    
    def is_exception_log(self, log_entry: Dict[str, Any]) -> bool:
        """Check if log entry contains an exception"""
        return log_entry.get('level') in ['ERROR', 'CRITICAL', 'FATAL']
    
    def extract_input_parameters(self, log_entry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract input parameters from log entry.
        These are the values that may have caused the exception.
        """
        # Exclude standard fields
        excluded_keys = {
            'timestamp', 'level', 'service', 'ip', 'trace_id', 'message', 'error',
            '_line_number', '_raw_payload', 'timestamp_parsed', 'log_id'
        }
        
        parameters = {}
        for key, value in log_entry.items():
            if key not in excluded_keys and not key.startswith('_'):
                parameters[key] = value
        
        return parameters
