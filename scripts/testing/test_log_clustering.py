#!/usr/bin/env python3
"""
Test script for log clustering strategies.
Demonstrates multi-level fingerprinting for logs without stack traces.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.services.log_normalizer import get_normalizer
from src.services.exception_extractor import ExceptionExtractor
from src.services.clustering import ExceptionClusterer
from typing import List, Dict, Any


def print_section(title: str):
    """Print a section header"""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def test_normalization():
    """Test message normalization"""
    print_section("TEST 1: Message Normalization")
    
    normalizer = get_normalizer()
    
    test_messages = [
        "User 12345 failed authentication at 2024-01-15T10:30:00Z",
        "User 67890 failed authentication at 2024-01-15T11:45:00Z",
        "Connection to 192.168.1.100:5432 refused",
        "Connection to 10.0.0.50:5432 refused",
        "Request to https://api.example.com/users/123 timeout after 30000ms",
        "Request to https://api.example.com/orders/456 timeout after 30000ms",
        "File /var/log/app.log not found",
        "File /var/log/error.log not found",
    ]
    
    print("Original Message → Normalized Message\n")
    for msg in test_messages:
        normalized = normalizer.normalize_message(msg)
        print(f"{msg}")
        print(f"  → {normalized}\n")


def test_fingerprinting():
    """Test multi-level fingerprinting"""
    print_section("TEST 2: Multi-Level Fingerprinting")
    
    normalizer = get_normalizer()
    
    test_cases = [
        {
            'message': "Connection failed to database db-prod-01.example.com:5432",
            'exception_type': "ConnectionError",
            'logger': "database.connector"
        },
        {
            'message': "Connection failed to database db-prod-02.example.com:5432",
            'exception_type': "ConnectionError",
            'logger': "database.connector"
        },
        {
            'message': "User 12345 authentication failed: invalid token",
            'exception_type': "AuthenticationError",
            'logger': "auth.service"
        },
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"Case {i}: {case['message']}\n")
        
        fingerprints = normalizer.generate_multi_level_fingerprints(
            message=case['message'],
            exception_type=case['exception_type'],
            logger_name=case['logger']
        )
        
        print(f"  Exception Type: {case['exception_type']}")
        print(f"  Logger: {case['logger']}")
        print(f"  Fingerprints:")
        print(f"    - Exact:    {fingerprints['exact']}")
        print(f"    - Template: {fingerprints['template']}")
        print(f"    - Semantic: {fingerprints['semantic']}")
        print(f"    - Category: {fingerprints['category']}")
        
        error_category = normalizer.extract_error_category(case['message'])
        print(f"  Error Category: {error_category}")
        
        key_terms = normalizer.extract_key_terms(case['message'])
        print(f"  Key Terms: {key_terms}\n")


def test_clustering_without_stack_trace():
    """Test clustering of logs without stack traces"""
    print_section("TEST 3: Clustering Logs Without Stack Traces")
    
    # Create mock log entries without stack traces
    mock_logs = [
        # Group 1: Database connection errors (should cluster together)
        {
            'level': 'ERROR',
            'message': 'Connection failed to db-prod-01.example.com:5432',
            'logger': 'database.connector',
            'log_id': 'log_001'
        },
        {
            'level': 'ERROR',
            'message': 'Connection failed to db-prod-02.example.com:5432',
            'logger': 'database.connector',
            'log_id': 'log_002'
        },
        {
            'level': 'ERROR',
            'message': 'Connection failed to db-staging.example.com:5432',
            'logger': 'database.connector',
            'log_id': 'log_003'
        },
        
        # Group 2: Authentication failures (should cluster together)
        {
            'level': 'ERROR',
            'message': 'User 12345 authentication failed: invalid token',
            'logger': 'auth.service',
            'log_id': 'log_004'
        },
        {
            'level': 'ERROR',
            'message': 'User 67890 authentication failed: invalid token',
            'logger': 'auth.service',
            'log_id': 'log_005'
        },
        
        # Group 3: Different auth error (separate cluster)
        {
            'level': 'ERROR',
            'message': 'User 11111 authentication failed: expired token',
            'logger': 'auth.service',
            'log_id': 'log_006'
        },
        
        # Group 4: API timeout errors (should cluster together)
        {
            'level': 'ERROR',
            'message': 'Request to https://api.example.com/users timeout after 30000ms',
            'logger': 'api.client',
            'log_id': 'log_007'
        },
        {
            'level': 'ERROR',
            'message': 'Request to https://api.example.com/orders timeout after 30000ms',
            'logger': 'api.client',
            'log_id': 'log_008'
        },
    ]
    
    # Extract exceptions
    extractor = ExceptionExtractor()
    exceptions = []
    
    print("Extracting exceptions from logs...\n")
    for log in mock_logs:
        exc = extractor.extract_exception(log)
        if exc:
            exceptions.append(exc)
            print(f"Log {log['log_id']}: {log['message']}")
            print(f"  → Template Fingerprint: {exc.get('fingerprint_template', 'N/A')}")
            print(f"  → Error Category: {exc.get('error_category', 'N/A')}\n")
    
    print(f"\nTotal exceptions extracted: {len(exceptions)}")
    print(f"Exceptions without stack trace: {sum(1 for e in exceptions if not e['has_stack_trace'])}")
    
    # Note: Actual clustering requires database and log_source_id
    # This demonstrates the extraction and fingerprinting process
    
    # Group by template fingerprint to show clustering
    print("\n" + "-"*80)
    print("Expected Clustering (by template fingerprint):\n")
    
    from collections import defaultdict
    clusters = defaultdict(list)
    
    for exc in exceptions:
        fp = exc.get('fingerprint_template', exc.get('fingerprint_static'))
        clusters[fp].append(exc)
    
    for i, (fingerprint, group) in enumerate(clusters.items(), 1):
        print(f"Cluster {i} (Fingerprint: {fingerprint}):")
        print(f"  Size: {len(group)} exceptions")
        print(f"  Error Category: {group[0].get('error_category', 'N/A')}")
        print(f"  Representative Message: {group[0]['exception_message']}")
        print(f"  Log IDs: {[e['log_id'] for e in group]}\n")


def test_similarity_matching():
    """Test similarity-based matching"""
    print_section("TEST 4: Similarity Matching")
    
    normalizer = get_normalizer()
    
    test_pairs = [
        (
            "Connection timeout to database server",
            "Connection timeout to database host",
            "Should match (same template)"
        ),
        (
            "User 123 failed login",
            "User 456 failed login",
            "Should match (same template)"
        ),
        (
            "File not found: /var/log/app.log",
            "File not found: /var/log/error.log",
            "Should match (same template)"
        ),
        (
            "Connection refused",
            "Authentication failed",
            "Should NOT match (different errors)"
        ),
    ]
    
    for msg1, msg2, expected in test_pairs:
        should_cluster, score, reason = normalizer.should_cluster_together(msg1, msg2)
        
        print(f"Message 1: {msg1}")
        print(f"Message 2: {msg2}")
        print(f"Expected: {expected}")
        print(f"Result: {'✅ MATCH' if should_cluster else '❌ NO MATCH'}")
        print(f"  Score: {score:.2f}")
        print(f"  Reason: {reason}\n")


def test_error_categories():
    """Test error category extraction"""
    print_section("TEST 5: Error Category Extraction")
    
    normalizer = get_normalizer()
    
    test_messages = [
        "Connection refused to database",
        "Request timeout after 30 seconds",
        "Authentication failed: invalid credentials",
        "SQL query failed: table not found",
        "Network error: host unreachable",
        "File not found: /var/log/app.log",
        "Out of memory: heap space exceeded",
        "Null pointer exception in user service",
        "Invalid input: malformed JSON",
        "Rate limit exceeded: too many requests",
    ]
    
    print("Message → Error Category\n")
    for msg in test_messages:
        category = normalizer.extract_error_category(msg)
        print(f"{msg}")
        print(f"  → {category or 'GENERIC'}\n")


def test_key_term_extraction():
    """Test key term extraction"""
    print_section("TEST 6: Key Term Extraction")
    
    normalizer = get_normalizer()
    
    test_messages = [
        "Database connection failed due to authentication error in production environment",
        "API request timeout while fetching user profile data from external service",
        "File system permission denied when writing logs to disk",
    ]
    
    print("Message → Key Terms\n")
    for msg in test_messages:
        terms = normalizer.extract_key_terms(msg, top_n=5)
        print(f"{msg}")
        print(f"  → {', '.join(terms)}\n")


def test_ngram_similarity():
    """Test n-gram similarity calculation"""
    print_section("TEST 7: N-Gram Similarity")
    
    normalizer = get_normalizer()
    
    test_pairs = [
        ("connection timeout to database server", "connection timeout to database host"),
        ("user authentication failed", "user authorization failed"),
        ("file not found error", "directory not found error"),
    ]
    
    for msg1, msg2 in test_pairs:
        ngrams1 = normalizer.generate_ngram_signature(msg1, n=3)
        ngrams2 = normalizer.generate_ngram_signature(msg2, n=3)
        similarity = normalizer.calculate_ngram_similarity(ngrams1, ngrams2)
        
        print(f"Message 1: {msg1}")
        print(f"  N-grams: {ngrams1}")
        print(f"Message 2: {msg2}")
        print(f"  N-grams: {ngrams2}")
        print(f"Similarity: {similarity:.2%}\n")


def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("  LOG CLUSTERING STRATEGIES - TEST SUITE")
    print("="*80)
    
    try:
        test_normalization()
        test_fingerprinting()
        test_clustering_without_stack_trace()
        test_similarity_matching()
        test_error_categories()
        test_key_term_extraction()
        test_ngram_similarity()
        
        print_section("ALL TESTS COMPLETED SUCCESSFULLY ✅")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
