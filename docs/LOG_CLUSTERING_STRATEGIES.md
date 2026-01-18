# Log Clustering Strategies for Logs Without Stack Traces

## Overview

This document describes the multi-level clustering strategies implemented in Luffy for efficiently grouping error logs, especially those **without stack traces**.

## Problem Statement

Error logs without stack traces are challenging to cluster because:
- No structural information (file, line number, function name)
- High variability in error messages (IDs, timestamps, URLs, etc.)
- Need to group semantically similar errors together
- Must avoid over-clustering (too broad) or under-clustering (too granular)

## Solution: Multi-Level Fingerprinting

We implement a **4-level fingerprinting hierarchy** that progressively relaxes matching criteria:

### Level 1: Exact Match
- **Strategy**: Hash the exact message
- **Use Case**: Identical error messages
- **Similarity**: 100%
- **Example**: 
  - `"Connection refused to database"`
  - `"Connection refused to database"` ✅ Match

### Level 2: Template Match (PRIMARY for logs without stack trace)
- **Strategy**: Normalize variables, then hash
- **Use Case**: Same error pattern with different variable values
- **Similarity**: ~95%
- **Normalization Rules**:
  - UUIDs → `<UUID>`
  - IP addresses → `<IP>`
  - URLs → `<URL>`
  - File paths → `<PATH>`
  - Timestamps → `<TIMESTAMP>`
  - Large numbers → `<NUMBER>`
  - Email addresses → `<EMAIL>`
  - JSON objects → `<JSON>`
  - Database IDs → `<ID>`

**Example**:
```
Original: "Connection failed to 192.168.1.100:5432 at 2024-01-15T10:30:00Z"
Normalized: "connection failed to <IP>:<NUMBER> at <TIMESTAMP>"

Original: "Connection failed to 10.0.0.50:5432 at 2024-01-15T11:45:00Z"
Normalized: "connection failed to <IP>:<NUMBER> at <TIMESTAMP>"
✅ Match (same template)
```

### Level 3: Semantic Match
- **Strategy**: Combine exception type + error category + normalized message
- **Use Case**: Similar errors from same component
- **Similarity**: ~80-90%
- **Components**:
  - Exception type (e.g., `ConnectionError`)
  - Error category (e.g., `CONNECTION_ERROR`, `TIMEOUT_ERROR`)
  - Logger name (e.g., `database.connector`)
  - First 100 chars of normalized message

**Example**:
```
Log 1: ConnectionError | CONNECTION_ERROR | database.connector | "failed to connect..."
Log 2: ConnectionError | CONNECTION_ERROR | database.connector | "unable to establish..."
✅ Match (same semantic context)
```

### Level 4: Category Match
- **Strategy**: Group by exception type + error category only
- **Use Case**: Broad error grouping for dashboards
- **Similarity**: ~60-70%
- **Categories**:
  - `CONNECTION_ERROR`
  - `TIMEOUT_ERROR`
  - `AUTH_ERROR`
  - `DATABASE_ERROR`
  - `NETWORK_ERROR`
  - `FILESYSTEM_ERROR`
  - `MEMORY_ERROR`
  - `NULL_ERROR`
  - `VALIDATION_ERROR`
  - `RATE_LIMIT_ERROR`

## Implementation Details

### 1. Log Normalization (`LogNormalizer` class)

**Key Methods**:

```python
from src.services.log_normalizer import get_normalizer

normalizer = get_normalizer()

# Normalize a message
normalized = normalizer.normalize_message(
    "User 12345 failed auth at 2024-01-15T10:30:00Z"
)
# Result: "user <NUMBER> failed auth at <TIMESTAMP>"

# Generate multi-level fingerprints
fingerprints = normalizer.generate_multi_level_fingerprints(
    message="Connection timeout to 192.168.1.100",
    exception_type="TimeoutError",
    logger_name="api.client"
)
# Returns:
# {
#     'exact': '3a7f8b2c1d4e5f6a',      # Exact hash
#     'template': '9e8d7c6b5a4f3e2d',   # Normalized template
#     'semantic': '1a2b3c4d5e6f7a8b',   # Type+category+message
#     'category': 'f1e2d3c4b5a69788'    # Type+category only
# }
```

### 2. Exception Extraction Enhancement

**Updated Flow**:

```python
# In ExceptionExtractor.extract_exception()

if stack_frames:
    # Traditional fingerprinting for logs WITH stack trace
    fingerprint_static = generate_static_fingerprint(exception_type, stack_frames)
else:
    # Multi-level fingerprinting for logs WITHOUT stack trace
    multi_fingerprints = normalizer.generate_multi_level_fingerprints(
        message=exception_message,
        exception_type=exception_type,
        logger_name=logger_name
    )
    
    # Use template as primary fingerprint
    fingerprint_static = multi_fingerprints['template']
    
    # Store all fingerprints for advanced clustering
    exception_data['fingerprint_template'] = multi_fingerprints['template']
    exception_data['fingerprint_semantic'] = multi_fingerprints['semantic']
    exception_data['fingerprint_category'] = multi_fingerprints['category']
    
    # Extract metadata
    exception_data['error_category'] = normalizer.extract_error_category(message)
    exception_data['key_terms'] = normalizer.extract_key_terms(message)
```

### 3. Clustering Logic

**Two-Path Clustering**:

```python
# In ExceptionClusterer.cluster_exceptions()

# Path 1: Logs WITH stack traces
with_stack = [exc for exc in exceptions if exc['has_stack_trace']]
for exc in with_stack:
    cluster_by_fingerprint(exc['fingerprint_static'])  # Traditional

# Path 2: Logs WITHOUT stack traces
without_stack = [exc for exc in exceptions if not exc['has_stack_trace']]
for exc in without_stack:
    cluster_by_fingerprint(exc['fingerprint_template'])  # Template-based
```

## Advanced Features

### 1. N-Gram Similarity

For fuzzy matching when template matching is too strict:

```python
# Generate 3-grams
ngrams1 = normalizer.generate_ngram_signature(
    "connection timeout to database", n=3
)
# ['connection timeout to', 'timeout to database']

ngrams2 = normalizer.generate_ngram_signature(
    "connection timeout to server", n=3
)
# ['connection timeout to', 'timeout to server']

# Calculate similarity
similarity = normalizer.calculate_ngram_similarity(ngrams1, ngrams2)
# Result: 0.5 (50% overlap)
```

### 2. Key Term Extraction

Extract important terms for similarity comparison:

```python
key_terms = normalizer.extract_key_terms(
    "Database connection failed due to authentication error"
)
# Result: ['database', 'connection', 'failed', 'authentication', 'error']
```

### 3. Structured Data Extraction

Identify presence of structured elements:

```python
structured = normalizer.extract_structured_data(message)
# Returns:
# {
#     'has_uuid': True,
#     'has_ip': True,
#     'has_url': False,
#     'has_path': True,
#     'has_timestamp': True,
#     'has_number': True,
#     'has_json': False,
#     'message_length': 150,
#     'word_count': 25
# }
```

### 4. Similarity Decision

Determine if two messages should cluster together:

```python
should_cluster, score, reason = normalizer.should_cluster_together(
    msg1="User 123 failed login at 10:30",
    msg2="User 456 failed login at 11:45",
    similarity_threshold=0.7
)
# Returns: (True, 0.95, 'template_match')
```

## Comparison with Traditional Methods

| Method | Pros | Cons | Best For |
|--------|------|------|----------|
| **Exact Hash** | Fast, precise | Too strict, misses similar errors | Identical messages |
| **Stack Trace** | Accurate, structural | Only works with stack traces | Java/Python exceptions |
| **Template Matching** ⭐ | Balances precision/recall | Requires good normalization | Logs without stack trace |
| **Semantic Clustering** | Flexible, context-aware | Can over-cluster | Broad grouping |
| **N-Gram Similarity** | Handles typos/variations | Computationally expensive | Fuzzy matching |
| **Category-Based** | Simple, fast | Too broad | High-level dashboards |

## Performance Characteristics

### Time Complexity

| Operation | Complexity | Notes |
|-----------|-----------|-------|
| Normalize message | O(n) | n = message length |
| Generate fingerprint | O(1) | Hash operation |
| Template matching | O(1) | Hash lookup |
| N-gram similarity | O(m*n) | m,n = n-gram counts |
| Key term extraction | O(n) | Tokenization + counting |

### Space Complexity

- **Per exception**: ~500 bytes (fingerprints + metadata)
- **Per cluster**: ~1 KB (representative + stats)
- **Normalizer patterns**: ~10 KB (compiled regexes)

## Configuration

### Similarity Thresholds

Adjust in `src/config/settings.py`:

```python
# Template matching threshold
TEMPLATE_SIMILARITY_THRESHOLD = 1.0  # Exact template match

# N-gram similarity threshold
NGRAM_SIMILARITY_THRESHOLD = 0.7  # 70% overlap

# Key term overlap threshold
KEY_TERM_OVERLAP_THRESHOLD = 0.6  # 60% term overlap
```

### Normalization Patterns

Add custom patterns in `LogNormalizer.__init__()`:

```python
self.normalization_patterns.append(
    (re.compile(r'custom_pattern'), '<PLACEHOLDER>')
)
```

### Error Categories

Add custom categories:

```python
self.error_category_patterns.append(
    (re.compile(r'your_pattern', re.IGNORECASE), 'YOUR_CATEGORY')
)
```

## Usage Examples

### Example 1: Database Connection Errors

**Input Logs**:
```
[ERROR] Connection failed to db-prod-01.example.com:5432
[ERROR] Connection failed to db-prod-02.example.com:5432
[ERROR] Connection failed to db-staging.example.com:5432
```

**Clustering Result**:
- **Cluster ID**: `cluster_9e8d7c6b5a4f`
- **Template**: `connection failed to <PATH>:<NUMBER>`
- **Category**: `CONNECTION_ERROR`
- **Size**: 3 exceptions
- **Representative**: First occurrence

### Example 2: Authentication Failures

**Input Logs**:
```
[ERROR] User 12345 authentication failed: invalid token
[ERROR] User 67890 authentication failed: expired token
[ERROR] User 11111 authentication failed: invalid token
```

**Clustering Result**:
- **Cluster ID**: `cluster_1a2b3c4d5e6f`
- **Template**: `user <NUMBER> authentication failed: invalid token`
- **Category**: `AUTH_ERROR`
- **Size**: 2 exceptions (12345, 11111)
- **Cluster ID**: `cluster_f1e2d3c4b5a6`
- **Template**: `user <NUMBER> authentication failed: expired token`
- **Size**: 1 exception (67890)

### Example 3: API Timeout Errors

**Input Logs**:
```
[ERROR] Request to https://api.example.com/users timeout after 30000ms
[ERROR] Request to https://api.example.com/orders timeout after 30000ms
[ERROR] Request to https://api.example.com/products timeout after 30000ms
```

**Clustering Result**:
- **Cluster ID**: `cluster_3a7f8b2c1d4e`
- **Template**: `request to <URL> timeout after <DURATION>`
- **Category**: `TIMEOUT_ERROR`
- **Size**: 3 exceptions

## Best Practices

### 1. Choose the Right Fingerprint Level

- **Exact**: Only for debugging/testing
- **Template**: Default for production (best balance)
- **Semantic**: When you need broader grouping
- **Category**: For high-level dashboards only

### 2. Monitor Cluster Sizes

```python
# Alert if cluster grows too large (over-clustering)
if cluster.cluster_size > 1000:
    logger.warning(f"Large cluster detected: {cluster.cluster_id}")
    # Consider splitting by semantic fingerprint
```

### 3. Validate Normalization

```python
# Test normalization patterns
test_messages = [
    "User 123 failed",
    "User 456 failed",
]
for msg in test_messages:
    normalized = normalizer.normalize_message(msg)
    print(f"{msg} → {normalized}")
# Should produce same normalized output
```

### 4. Use Metadata for RCA

```python
# Leverage extracted metadata in RCA generation
if cluster.error_category == 'CONNECTION_ERROR':
    # Focus on network/connectivity issues
    rca_prompt += "Analyze network connectivity and firewall rules"
elif cluster.error_category == 'AUTH_ERROR':
    # Focus on authentication/authorization
    rca_prompt += "Analyze authentication flow and token validation"
```

## Future Enhancements

### 1. Machine Learning-Based Clustering

- Train embedding model on historical logs
- Use cosine similarity for semantic matching
- Adaptive threshold based on cluster quality

### 2. Hierarchical Clustering

- Build cluster hierarchy (category → semantic → template → exact)
- Allow drill-down from broad to specific
- Better visualization in UI

### 3. Anomaly Detection

- Detect outlier logs that don't fit any cluster
- Flag new error patterns for investigation
- Auto-create alerts for novel errors

### 4. Cross-Service Clustering

- Identify similar errors across different services
- Detect systemic issues (e.g., database outage affecting all services)
- Correlate errors with infrastructure events

## Troubleshooting

### Issue: Too Many Small Clusters

**Cause**: Template matching too strict
**Solution**: Use semantic fingerprinting or increase n-gram threshold

```python
# Switch to semantic clustering
clustering_strategy = 'semantic'
```

### Issue: Too Few Large Clusters

**Cause**: Over-normalization or category-based clustering
**Solution**: Use template fingerprinting or add more specific patterns

```python
# Add more specific normalization patterns
normalizer.normalization_patterns.append(
    (re.compile(r'specific_pattern'), '<SPECIFIC>')
)
```

### Issue: Unrelated Logs in Same Cluster

**Cause**: Insufficient normalization or too broad category
**Solution**: Add more normalization patterns or use template matching

```python
# Add pattern to differentiate
normalizer.normalization_patterns.insert(0,  # Insert at beginning
    (re.compile(r'critical_differentiator'), '<DIFF>')
)
```

## Conclusion

The multi-level fingerprinting approach provides:

✅ **Efficient clustering** of logs without stack traces
✅ **Balanced precision and recall** through template matching
✅ **Flexibility** with 4 fingerprint levels
✅ **Scalability** with O(1) hash lookups
✅ **Extensibility** through configurable patterns

This enables effective exception clustering even when structural information (stack traces) is unavailable, making Luffy suitable for a wide variety of log formats and error types.
