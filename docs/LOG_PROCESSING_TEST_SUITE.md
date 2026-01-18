# Complete Log Processing Flow Test Suite

## Overview

This document describes the comprehensive test suite for the Luffy log processing pipeline. The test suite validates all aspects of log ingestion, processing, clustering, and analysis with different log types and scenarios.

**Author:** Senior Software Engineer  
**Date:** 2025-12-25  
**Version:** 1.0

---

## Table of Contents

1. [Test Coverage](#test-coverage)
2. [Test Files](#test-files)
3. [Running Tests](#running-tests)
4. [Test Categories](#test-categories)
5. [Log Types Tested](#log-types-tested)
6. [Test Scenarios](#test-scenarios)
7. [CI/CD Integration](#cicd-integration)
8. [Troubleshooting](#troubleshooting)

---

## Test Coverage

### Components Tested

✅ **Log Parsing** (`src/ingestion/log_parser.py`)
- JSON log parsing
- Different log formats
- Error handling

✅ **Exception Extraction** (`src/services/exception_extractor.py`)
- Stack trace parsing (Python, Java, JavaScript)
- Multi-level fingerprinting
- Template matching
- Semantic analysis

✅ **Exception Clustering** (`src/services/clustering.py`)
- Fingerprint-based clustering
- Template-based clustering
- Service isolation
- Time-based filtering

✅ **Log Processing Pipeline** (`src/services/processor.py`)
- End-to-end processing
- Statistics tracking
- Notification triggering

✅ **API Ingestion** (`src/services/api_ingest.py`)
- Authentication/Authorization
- Input validation
- Rate limiting
- Duplicate detection
- Batch processing

✅ **Service Isolation**
- Multi-service processing
- Service-specific clustering
- Log source association

---

## Test Files

### 1. `tests/test_complete_log_processing_flow.py`

**Purpose:** Tests the complete log processing pipeline end-to-end

**Test Classes:**
- `TestLogParser` - Log parsing functionality
- `TestExceptionExtractor` - Exception extraction
- `TestExceptionClusterer` - Clustering logic
- `TestLogProcessor` - Complete pipeline
- `TestAPIIngestion` - API validation
- `TestBatchProcessing` - Batch operations
- `TestServiceIsolation` - Multi-service support
- `TestEndToEndFlow` - Complete workflows
- `TestIntegration` - Integration tests
- `TestPerformance` - Performance tests

**Total Tests:** 20+ test functions

### 2. `tests/test_fluent_bit_ingestion.py`

**Purpose:** Tests Fluent Bit API ingestion with real-world log formats

**Test Classes:**
- `TestAuthentication` - API authentication
- `TestLogIngestion` - Log ingestion flows
- `TestInputValidation` - Input validation
- `TestRateLimiting` - Rate limiting
- `TestDuplicateDetection` - Duplicate handling
- `TestHealthCheck` - Health endpoints
- `TestErrorHandling` - Error scenarios

**Total Tests:** 15+ test functions

---

## Running Tests

### Quick Start

```bash
# Run all log processing tests
bash scripts/testing/run_log_processing_tests.sh
```

### Individual Test Suites

```bash
# Run complete flow tests
pytest tests/test_complete_log_processing_flow.py -v

# Run API ingestion tests
pytest tests/test_fluent_bit_ingestion.py -v

# Run specific test class
pytest tests/test_complete_log_processing_flow.py::TestExceptionClusterer -v

# Run specific test function
pytest tests/test_complete_log_processing_flow.py::TestExceptionClusterer::test_cluster_exceptions_with_stack -v
```

### With Coverage

```bash
# Generate coverage report
pytest tests/test_complete_log_processing_flow.py \
    --cov=src/services \
    --cov=src/ingestion \
    --cov-report=html \
    --cov-report=term-missing
```

### Integration Tests

```bash
# Run integration tests (requires database/services)
RUN_INTEGRATION_TESTS=true bash scripts/testing/run_log_processing_tests.sh
```

---

## Test Categories

### 1. Unit Tests

Test individual components in isolation with mocked dependencies.

**Examples:**
- `test_extract_exception_with_stack()` - Tests exception extractor
- `test_parse_valid_log()` - Tests log parser
- `test_generate_log_hash()` - Tests hash generation

### 2. Integration Tests

Test components working together with real dependencies.

**Examples:**
- `test_real_database_clustering()` - Tests with actual database
- `test_celery_task_execution()` - Tests with Celery worker

**Note:** Integration tests are marked with `@pytest.mark.integration`

### 3. End-to-End Tests

Test complete workflows from API to database.

**Examples:**
- `test_complete_flow_python_exceptions()` - Full Python exception flow
- `test_complete_flow_mixed_exceptions()` - Mixed exception types

### 4. Performance Tests

Test system performance with large datasets.

**Examples:**
- `test_large_batch_processing()` - 1000 logs processing

---

## Log Types Tested

### 1. Python Exceptions (with Stack Trace)

```python
{
    "exception_type": "ValueError",
    "exception_message": "Invalid user ID",
    "stack_trace": "Traceback (most recent call last):\n  File ..."
}
```

**Tests:**
- Stack trace parsing
- Fingerprint generation
- Traditional clustering

### 2. Java Exceptions (with Stack Trace)

```python
{
    "exception_type": "SQLException",
    "exception_message": "Connection timeout",
    "stack_trace": "java.sql.SQLException: Connection timeout\n    at ..."
}
```

**Tests:**
- Java stack trace parsing
- Multi-language support
- Caused by chain handling

### 3. JavaScript Exceptions (with Stack Trace)

```python
{
    "exception_type": "TypeError",
    "exception_message": "Cannot read property 'name' of undefined",
    "stack_trace": "TypeError: Cannot read property...\n    at ..."
}
```

**Tests:**
- JavaScript stack parsing
- Browser/Node.js formats

### 4. Errors Without Stack Traces

```python
{
    "level": "ERROR",
    "message": "Payment processing failed for order #12345"
}
```

**Tests:**
- Template-based fingerprinting
- Semantic fingerprinting
- Category-based clustering

### 5. Different Log Levels

- `ERROR` - Error logs
- `FATAL` - Fatal errors
- `CRITICAL` - Critical errors
- `WARNING` - Warning logs
- `INFO` - Info logs (filtered out)

---

## Test Scenarios

### Scenario 1: Single Service, Single Exception Type

**Setup:**
- 1 service: "web-api"
- 5 identical Python exceptions
- 1 log source

**Expected:**
- 1 cluster created
- 5 exceptions in cluster
- Correct service association

**Test:** `test_cluster_exceptions_with_stack()`

### Scenario 2: Single Service, Multiple Exception Types

**Setup:**
- 1 service: "web-api"
- Python, Java, JavaScript exceptions
- Errors with/without stack traces

**Expected:**
- Multiple clusters (different types)
- Correct clustering strategy per type
- All associated with same service

**Test:** `test_complete_flow_mixed_exceptions()`

### Scenario 3: Multiple Services, Same Exception Type

**Setup:**
- 2 services: "service-1", "service-2"
- Identical exceptions in both

**Expected:**
- 2 separate clusters (service isolation)
- No cross-service contamination

**Test:** `test_service_specific_clustering()`

### Scenario 4: Template-Based Clustering

**Setup:**
- Errors without stack traces
- Similar message patterns
- Different variable values

**Expected:**
- Clustered by template pattern
- Variables normalized
- Semantic similarity considered

**Test:** `test_cluster_exceptions_without_stack_same_template()`

### Scenario 5: High-Volume Batch Processing

**Setup:**
- 1000 logs in single batch
- Mixed exception types
- Rate limiting enabled

**Expected:**
- All logs processed
- Performance within limits
- No data loss

**Test:** `test_large_batch_processing()`

### Scenario 6: API Authentication & Authorization

**Setup:**
- Valid/invalid tokens
- Active/inactive services
- Missing authorization headers

**Expected:**
- 401 for invalid auth
- 403 for inactive services
- 200 for valid requests

**Tests:** `TestAuthentication` class

### Scenario 7: Duplicate Detection

**Setup:**
- Same log sent multiple times
- Within deduplication window

**Expected:**
- First occurrence accepted
- Duplicates filtered
- Deduplication cache updated

**Test:** `test_duplicate_detection()`

### Scenario 8: Rate Limiting

**Setup:**
- Requests exceeding rate limit
- Different services

**Expected:**
- 429 when limit exceeded
- Per-service rate tracking
- Remaining count accurate

**Test:** `test_rate_limit_enforcement()`

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Log Processing Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov pytest-mock
    
    - name: Run tests
      run: |
        bash scripts/testing/run_log_processing_tests.sh
    
    - name: Upload coverage
      uses: codecov/codecov-action@v2
      with:
        files: ./test_results/coverage.xml
```

### Jenkins Example

```groovy
pipeline {
    agent any
    
    stages {
        stage('Test') {
            steps {
                sh 'pip install -r requirements.txt'
                sh 'bash scripts/testing/run_log_processing_tests.sh'
            }
        }
        
        stage('Publish Results') {
            steps {
                junit 'test_results/junit_*.xml'
                publishHTML([
                    reportDir: 'test_results/coverage_processing',
                    reportFiles: 'index.html',
                    reportName: 'Coverage Report'
                ])
            }
        }
    }
}
```

---

## Troubleshooting

### Common Issues

#### 1. Import Errors

**Problem:** `ModuleNotFoundError: No module named 'src'`

**Solution:**
```bash
# Add project root to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Or install in editable mode
pip install -e .
```

#### 2. Database Connection Errors

**Problem:** Tests fail with database connection errors

**Solution:**
```bash
# Use mocked database for unit tests
# Integration tests require actual database

# Skip integration tests
pytest tests/ -m "not integration"
```

#### 3. Celery Task Errors

**Problem:** `celery.exceptions.NotRegistered`

**Solution:**
```bash
# Ensure Celery app is properly imported
# Mock Celery tasks in unit tests

# Example mock
@patch('src.services.tasks.process_log_batch')
def test_function(mock_task):
    mock_task.delay.return_value = Mock(id="task-123")
```

#### 4. Fixture Not Found

**Problem:** `fixture 'sample_service' not found`

**Solution:**
```bash
# Ensure fixtures are in same file or conftest.py
# Check fixture scope (function, class, module, session)
```

#### 5. Slow Tests

**Problem:** Tests taking too long

**Solution:**
```bash
# Run tests in parallel
pytest tests/ -n auto

# Run specific test class
pytest tests/test_complete_log_processing_flow.py::TestLogParser

# Skip performance tests
pytest tests/ -m "not performance"
```

---

## Test Data

### Sample Log Formats

All test fixtures use realistic log formats from:
- **Fluent Bit** - Kubernetes log collector
- **Django** - Python web framework
- **Spring Boot** - Java framework
- **Express.js** - Node.js framework
- **Nginx** - Web server

### Fixture Files

Test data is defined as pytest fixtures in test files:
- `fluent_bit_python_log` - Python exception from Django
- `fluent_bit_java_log` - Java exception from Spring Boot
- `fluent_bit_nodejs_log` - Node.js exception from Express
- `fluent_bit_error_without_stack` - Nginx error log

---

## Metrics & KPIs

### Test Coverage Goals

- **Line Coverage:** > 80%
- **Branch Coverage:** > 70%
- **Function Coverage:** > 90%

### Performance Benchmarks

- **Single log processing:** < 100ms
- **Batch (100 logs):** < 5 seconds
- **Batch (1000 logs):** < 30 seconds
- **API response time:** < 200ms

### Quality Metrics

- **Test Pass Rate:** > 95%
- **Flaky Tests:** < 5%
- **Test Execution Time:** < 5 minutes

---

## Future Enhancements

### Planned Test Additions

1. **Load Testing**
   - Concurrent request handling
   - Database connection pooling
   - Memory usage under load

2. **Security Testing**
   - SQL injection attempts
   - XSS in log messages
   - Token brute force

3. **Chaos Testing**
   - Database failures
   - Network timeouts
   - Service unavailability

4. **Multi-Language Support**
   - Go exceptions
   - Rust panics
   - C++ exceptions

---

## References

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-cov Documentation](https://pytest-cov.readthedocs.io/)
- [Fluent Bit Documentation](https://docs.fluentbit.io/)
- [Luffy Architecture Guide](./ARCHITECTURE_AND_DEPLOYMENT.md)

---

## Support

For questions or issues with the test suite:

1. Check this documentation
2. Review test code comments
3. Check CI/CD logs
4. Contact the development team

---

**Last Updated:** 2025-12-25  
**Maintained By:** Engineering Team
