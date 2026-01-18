"""
Log normalization and fingerprinting for logs without stack traces.
Implements multiple strategies for clustering similar error logs.
"""
import re
import hashlib
from typing import Dict, Any, List, Optional, Tuple
import logging
from collections import Counter

logger = logging.getLogger(__name__)


class LogNormalizer:
    """
    Normalize and fingerprint error logs without stack traces.
    
    Strategies:
    1. Template-based normalization (replace variables with placeholders)
    2. Semantic fingerprinting (hash normalized patterns)
    3. N-gram similarity for fuzzy matching
    4. Entity extraction (IDs, URLs, numbers, etc.)
    """
    
    def __init__(self):
        # Patterns for variable data that should be normalized
        self.normalization_patterns = [
            # UUIDs
            (re.compile(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', re.IGNORECASE), '<UUID>'),
            # Hex IDs (8+ chars)
            (re.compile(r'\b0x[0-9a-f]{8,}\b', re.IGNORECASE), '<HEX_ID>'),
            # IP addresses
            (re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'), '<IP>'),
            # Email addresses
            (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), '<EMAIL>'),
            # URLs
            (re.compile(r'https?://[^\s]+'), '<URL>'),
            # File paths (Unix/Windows)
            (re.compile(r'(?:/[\w.-]+)+|(?:[A-Z]:\\[\w\\.-]+)'), '<PATH>'),
            # Timestamps (ISO format)
            (re.compile(r'\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?'), '<TIMESTAMP>'),
            # Large numbers (4+ digits)
            (re.compile(r'\b\d{4,}\b'), '<NUMBER>'),
            # Decimal numbers
            (re.compile(r'\b\d+\.\d+\b'), '<DECIMAL>'),
            # Memory addresses
            (re.compile(r'\b0x[0-9a-fA-F]+\b'), '<ADDR>'),
            # Database IDs (common patterns)
            (re.compile(r'\bid[=:]\s*\d+\b', re.IGNORECASE), 'id=<ID>'),
            (re.compile(r'\buser_id[=:]\s*\d+\b', re.IGNORECASE), 'user_id=<ID>'),
            (re.compile(r'\border_id[=:]\s*\d+\b', re.IGNORECASE), 'order_id=<ID>'),
            # JSON-like structures (simplified)
            (re.compile(r'\{[^}]{20,}\}'), '<JSON>'),
            # Array-like structures
            (re.compile(r'\[[^\]]{20,}\]'), '<ARRAY>'),
            # Quoted strings (preserve short ones, replace long ones)
            (re.compile(r'"[^"]{30,}"'), '<STRING>'),
            (re.compile(r"'[^']{30,}'"), '<STRING>'),
            # Duration/time values
            (re.compile(r'\b\d+\s*(?:ms|sec|min|hour|day)s?\b', re.IGNORECASE), '<DURATION>'),
            # Percentages
            (re.compile(r'\b\d+(?:\.\d+)?%'), '<PERCENT>'),
            # Version numbers
            (re.compile(r'\bv?\d+\.\d+(?:\.\d+)?(?:\.\d+)?\b'), '<VERSION>'),
        ]
        
        # Patterns for extracting error categories
        self.error_category_patterns = [
            # Connection errors
            (re.compile(r'connection\s+(?:refused|timeout|reset|failed|closed)', re.IGNORECASE), 'CONNECTION_ERROR'),
            # Timeout errors
            (re.compile(r'timeout|timed\s+out', re.IGNORECASE), 'TIMEOUT_ERROR'),
            # Authentication errors
            (re.compile(r'auth(?:entication|orization)?\s+(?:failed|denied|error)', re.IGNORECASE), 'AUTH_ERROR'),
            # Database errors
            (re.compile(r'database|sql|query|table|column', re.IGNORECASE), 'DATABASE_ERROR'),
            # Network errors
            (re.compile(r'network|socket|host|dns', re.IGNORECASE), 'NETWORK_ERROR'),
            # File system errors
            (re.compile(r'file\s+not\s+found|no\s+such\s+file|permission\s+denied', re.IGNORECASE), 'FILESYSTEM_ERROR'),
            # Memory errors
            (re.compile(r'out\s+of\s+memory|memory\s+error|heap', re.IGNORECASE), 'MEMORY_ERROR'),
            # Null/None errors
            (re.compile(r'null\s+pointer|none\s+type|undefined', re.IGNORECASE), 'NULL_ERROR'),
            # Validation errors
            (re.compile(r'invalid|validation|malformed|bad\s+request', re.IGNORECASE), 'VALIDATION_ERROR'),
            # Rate limit errors
            (re.compile(r'rate\s+limit|too\s+many\s+requests|quota', re.IGNORECASE), 'RATE_LIMIT_ERROR'),
        ]
    
    def normalize_message(self, message: str) -> str:
        """
        Normalize a log message by replacing variable data with placeholders.
        
        Args:
            message: Raw log message
            
        Returns:
            Normalized message with placeholders
        """
        if not message:
            return ""
        
        normalized = message
        
        # Apply all normalization patterns
        for pattern, replacement in self.normalization_patterns:
            normalized = pattern.sub(replacement, normalized)
        
        # Normalize whitespace
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        # Convert to lowercase for better matching
        normalized = normalized.lower()
        
        return normalized
    
    def extract_error_category(self, message: str) -> Optional[str]:
        """
        Extract error category from message.
        
        Args:
            message: Log message
            
        Returns:
            Error category or None
        """
        for pattern, category in self.error_category_patterns:
            if pattern.search(message):
                return category
        return None
    
    def generate_template_fingerprint(self, message: str) -> str:
        """
        Generate fingerprint based on normalized template.
        
        Args:
            message: Raw log message
            
        Returns:
            16-character hex fingerprint
        """
        normalized = self.normalize_message(message)
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]
    
    def generate_semantic_fingerprint(
        self,
        message: str,
        exception_type: str = 'UnknownError',
        logger_name: str = 'unknown',
        error_category: Optional[str] = None
    ) -> str:
        """
        Generate semantic fingerprint combining multiple attributes.
        
        Args:
            message: Log message
            exception_type: Exception type
            logger_name: Logger name
            error_category: Error category
            
        Returns:
            16-character hex fingerprint
        """
        normalized_msg = self.normalize_message(message)
        category = error_category or self.extract_error_category(message) or 'GENERIC'
        
        # Combine semantic components
        components = [
            exception_type,
            category,
            logger_name,
            normalized_msg[:100]  # First 100 chars of normalized message
        ]
        
        fingerprint_str = '|'.join(components)
        return hashlib.sha256(fingerprint_str.encode()).hexdigest()[:16]
    
    def extract_key_terms(self, message: str, top_n: int = 5) -> List[str]:
        """
        Extract key terms from message for similarity comparison.
        
        Args:
            message: Log message
            top_n: Number of top terms to extract
            
        Returns:
            List of key terms
        """
        # Normalize first
        normalized = self.normalize_message(message)
        
        # Remove common stop words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
            'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'should', 'could', 'may', 'might', 'can', 'this', 'that',
            'these', 'those', 'it', 'its', 'i', 'you', 'he', 'she', 'we', 'they'
        }
        
        # Tokenize and filter
        words = re.findall(r'\b[a-z]{3,}\b', normalized)
        filtered_words = [w for w in words if w not in stop_words]
        
        # Count frequency
        word_counts = Counter(filtered_words)
        
        # Return top N
        return [word for word, _ in word_counts.most_common(top_n)]
    
    def generate_ngram_signature(self, message: str, n: int = 3) -> List[str]:
        """
        Generate n-gram signature for fuzzy matching.
        
        Args:
            message: Log message
            n: N-gram size
            
        Returns:
            List of n-grams
        """
        normalized = self.normalize_message(message)
        words = normalized.split()
        
        ngrams = []
        for i in range(len(words) - n + 1):
            ngram = ' '.join(words[i:i+n])
            ngrams.append(ngram)
        
        return ngrams
    
    def calculate_ngram_similarity(self, ngrams1: List[str], ngrams2: List[str]) -> float:
        """
        Calculate Jaccard similarity between two n-gram sets.
        
        Args:
            ngrams1: First n-gram list
            ngrams2: Second n-gram list
            
        Returns:
            Similarity score (0.0 to 1.0)
        """
        if not ngrams1 or not ngrams2:
            return 0.0
        
        set1 = set(ngrams1)
        set2 = set(ngrams2)
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        return intersection / union if union > 0 else 0.0
    
    def extract_structured_data(self, message: str) -> Dict[str, Any]:
        """
        Extract structured data from message for better clustering.
        
        Args:
            message: Log message
            
        Returns:
            Dictionary of extracted entities
        """
        entities = {
            'has_uuid': bool(re.search(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', message, re.IGNORECASE)),
            'has_ip': bool(re.search(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', message)),
            'has_url': bool(re.search(r'https?://', message)),
            'has_path': bool(re.search(r'(?:/[\w.-]+)+|(?:[A-Z]:\\[\w\\.-]+)', message)),
            'has_timestamp': bool(re.search(r'\d{4}-\d{2}-\d{2}', message)),
            'has_number': bool(re.search(r'\b\d+\b', message)),
            'has_json': bool(re.search(r'\{.*\}', message)),
            'message_length': len(message),
            'word_count': len(message.split()),
        }
        
        return entities
    
    def generate_multi_level_fingerprints(
        self,
        message: str,
        exception_type: str = 'UnknownError',
        logger_name: str = 'unknown'
    ) -> Dict[str, str]:
        """
        Generate multiple fingerprints at different granularity levels.
        
        Returns:
            Dictionary with different fingerprint types:
            - exact: Exact message match
            - template: Normalized template match
            - semantic: Semantic similarity match
            - category: Error category match
        """
        error_category = self.extract_error_category(message)
        
        fingerprints = {
            # Level 1: Exact match (for identical messages)
            'exact': hashlib.sha256(message.encode()).hexdigest()[:16],
            
            # Level 2: Template match (normalized variables)
            'template': self.generate_template_fingerprint(message),
            
            # Level 3: Semantic match (type + category + normalized message)
            'semantic': self.generate_semantic_fingerprint(
                message, exception_type, logger_name, error_category
            ),
            
            # Level 4: Category match (error type + category)
            'category': hashlib.sha256(
                f"{exception_type}|{error_category or 'GENERIC'}".encode()
            ).hexdigest()[:16],
        }
        
        return fingerprints
    
    def should_cluster_together(
        self,
        msg1: str,
        msg2: str,
        similarity_threshold: float = 0.7
    ) -> Tuple[bool, float, str]:
        """
        Determine if two messages should be clustered together.
        
        Args:
            msg1: First message
            msg2: Second message
            similarity_threshold: Minimum similarity score
            
        Returns:
            Tuple of (should_cluster, similarity_score, match_reason)
        """
        # Level 1: Exact match
        if msg1 == msg2:
            return True, 1.0, 'exact_match'
        
        # Level 2: Template match
        norm1 = self.normalize_message(msg1)
        norm2 = self.normalize_message(msg2)
        if norm1 == norm2:
            return True, 0.95, 'template_match'
        
        # Level 3: N-gram similarity
        ngrams1 = self.generate_ngram_signature(msg1, n=3)
        ngrams2 = self.generate_ngram_signature(msg2, n=3)
        ngram_sim = self.calculate_ngram_similarity(ngrams1, ngrams2)
        
        if ngram_sim >= similarity_threshold:
            return True, ngram_sim, 'ngram_similarity'
        
        # Level 4: Key term overlap
        terms1 = set(self.extract_key_terms(msg1))
        terms2 = set(self.extract_key_terms(msg2))
        
        if terms1 and terms2:
            term_overlap = len(terms1 & terms2) / len(terms1 | terms2)
            if term_overlap >= similarity_threshold:
                return True, term_overlap, 'key_term_overlap'
        
        return False, 0.0, 'no_match'


# Singleton instance
_normalizer_instance = None

def get_normalizer() -> LogNormalizer:
    """Get singleton normalizer instance"""
    global _normalizer_instance
    if _normalizer_instance is None:
        _normalizer_instance = LogNormalizer()
    return _normalizer_instance
