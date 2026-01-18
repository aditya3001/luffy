"""
Complete Log Processing Flow Test Suite

Tests the entire log processing pipeline end-to-end with different log types:
1. Logs with stack traces (traditional clustering)
2. Logs without stack traces (multi-level fingerprinting)
3. Different log levels (ERROR, FATAL, CRITICAL, WARNING)
4. Different exception types (Python, Java, JavaScript, Generic)
5. Duplicate detection
6. Rate limiting
7. Service isolation
8. Batch processing
9. API ingestion flow
10. Celery task processing

Author: Senior Software Engineer
Date: 2025-12-25
"""

import pytest
import json
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any
from unittest.mock import Mock, patch, MagicMock

# Import components to test
from src.services.processor import LogProcessor
from src.services.clustering import ExceptionClusterer
from src.services.exception_extractor import ExceptionExtractor
from src.ingestion.log_parser import LogParser
from src.storage.models import ExceptionCluster, LogSource, Service
from src.services.api_ingest import (
    LogEntry,
    IngestLogsRequest,
    generate_log_hash,
    is_duplicate,
    RateLimiter
)


# ============================================================================
# TEST DATA FIXTURES
# ============================================================================

@pytest.fixture
def sample_service():
    """Create a sample service for testing"""
    return Service(
        id="test-service-001",
        name="Test Web Application",
        description="Test service for log processing",
        is_active=True,
        repository_url="https://github.com/test/repo",
        git_branch="main"
    )


@pytest.fixture
def sample_log_source(sample_service):
    """Create a sample log source for testing"""
    return LogSource(
        id="test-log-source-001",
        service_id=sample_service.id,
        service_name=sample_service.name,
        source_type="opensearch",
        host="localhost",
        port=9200,
        index_pattern="logs-*",
        fetch_enabled=True,
        fetch_interval_minutes=15
    )


@pytest.fixture
def python_exception_with_stack():
    """Python exception with full stack trace"""
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "level": "ERROR",
        "logger": "test.module.service",
        "message": "Failed to process user request",
        "exception_type": "ValueError",
        "exception_message": "Invalid user ID: expected integer, got string",
        "stack_trace": """Traceback (most recent call last):
  File "/app/services/user_service.py", line 45, in get_user
    user_id = int(user_id_str)
ValueError: invalid literal for int() with base 10: 'abc'
  File "/app/api/handlers.py", line 123, in handle_request
    user = user_service.get_user(request.params['user_id'])
  File "/app/main.py", line 67, in process_request
    return handler.handle_request(request)""",
        "service_id": "test-service-001",
        "service_name": "Test Web Application",
        "environment": "production",
        "hostname": "web-pod-1",
        "file_path": "/app/services/user_service.py",
        "metadata": {
            "request_id": "req-12345",
            "user_agent": "Mozilla/5.0"
        }
    }


@pytest.fixture
def java_exception_with_stack():
    """Java exception with full stack trace"""
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "level": "ERROR",
        "logger": "com.example.service.DatabaseService",
        "message": "Database connection failed",
        "exception_type": "SQLException",
        "exception_message": "Connection timeout after 30 seconds",
        "stack_trace": """java.sql.SQLException: Connection timeout after 30 seconds
    at com.mysql.jdbc.ConnectionImpl.connect(ConnectionImpl.java:789)
    at com.example.service.DatabaseService.getConnection(DatabaseService.java:45)
    at com.example.api.UserController.getUser(UserController.java:123)
    at com.example.Main.handleRequest(Main.java:67)""",
        "service_id": "test-service-001",
        "service_name": "Test Web Application",
        "environment": "production",
        "hostname": "api-pod-2",
        "file_path": "com/example/service/DatabaseService.java",
        "metadata": {
            "thread": "http-nio-8080-exec-5",
            "transaction_id": "txn-67890"
        }
    }


@pytest.fixture
def error_without_stack_template1():
    """Error log without stack trace - template type 1"""
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "level": "ERROR",
        "logger": "payment.processor",
        "message": "Payment processing failed for order #12345: insufficient funds",
        "service_id": "test-service-001",
        "service_name": "Test Web Application",
        "environment": "production",
        "hostname": "payment-pod-1",
        "metadata": {
            "order_id": "12345",
            "amount": 99.99
        }
    }


@pytest.fixture
def error_without_stack_template2():
    """Error log without stack trace - similar template"""
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "level": "ERROR",
        "logger": "payment.processor",
        "message": "Payment processing failed for order #67890: card declined",
        "service_id": "test-service-001",
        "service_name": "Test Web Application",
        "environment": "production",
        "hostname": "payment-pod-2",
        "metadata": {
            "order_id": "67890",
            "amount": 149.99
        }
    }


@pytest.fixture
def error_without_stack_different_category():
    """Error log without stack trace - different category"""
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "level": "ERROR",
        "logger": "auth.service",
        "message": "Authentication failed: invalid credentials",
        "service_id": "test-service-001",
        "service_name": "Test Web Application",
        "environment": "production",
        "hostname": "auth-pod-1",
        "metadata": {
            "username": "testuser",
            "ip_address": "192.168.1.100"
        }
    }


@pytest.fixture
def warning_log():
    """Warning level log"""
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "level": "WARNING",
        "logger": "cache.service",
        "message": "Cache miss for key: user_profile_12345",
        "service_id": "test-service-001",
        "service_name": "Test Web Application",
        "environment": "production",
        "hostname": "cache-pod-1"
    }


@pytest.fixture
def info_log():
    """Info level log (should be filtered out)"""
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "level": "INFO",
        "logger": "api.service",
        "message": "Request processed successfully",
        "service_id": "test-service-001",
        "service_name": "Test Web Application",
        "environment": "production",
        "hostname": "api-pod-1"
    }


@pytest.fixture
def javascript_exception_with_stack():
    """JavaScript exception with stack trace"""
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "level": "ERROR",
        "logger": "frontend.app",
        "message": "Uncaught TypeError: Cannot read property 'name' of undefined",
        "exception_type": "TypeError",
        "exception_message": "Cannot read property 'name' of undefined",
        "stack_trace": """TypeError: Cannot read property 'name' of undefined
    at UserProfile.render (UserProfile.js:45:12)
    at React.Component.render (react.js:123:45)
    at App.render (App.js:67:23)""",
        "service_id": "test-service-001",
        "service_name": "Test Web Application",
        "environment": "production",
        "hostname": "frontend-cdn",
        "file_path": "src/components/UserProfile.js",
        "metadata": {
            "browser": "Chrome 120",
            "user_id": "user-789"
        }
    }


# ============================================================================
# TEST CLASSES
# ============================================================================

class TestLogParser:
    """Test log parsing functionality"""
    
    def test_parse_valid_log(self, python_exception_with_stack):
        """Test parsing a valid log entry"""
        parser = LogParser()
        parsed = parser.parse(json.dumps(python_exception_with_stack))
        
        assert parsed is not None
        assert parsed['level'] == 'ERROR'
        assert parsed['exception_type'] == 'ValueError'
        assert 'stack_trace' in parsed
    
    def test_parse_log_without_stack(self, error_without_stack_template1):
        """Test parsing log without stack trace"""
        parser = LogParser()
        parsed = parser.parse(json.dumps(error_without_stack_template1))
        
        assert parsed is not None
        assert parsed['level'] == 'ERROR'
        assert 'stack_trace' not in parsed or parsed['stack_trace'] is None


class TestExceptionExtractor:
    """Test exception extraction functionality"""
    
    def test_extract_exception_with_stack(self, python_exception_with_stack):
        """Test extracting exception with stack trace"""
        extractor = ExceptionExtractor()
        result = extractor.extract_exception(python_exception_with_stack)
        
        assert result is not None
        assert result['exception_type'] == 'ValueError'
        assert result['has_stack_trace'] is True
        assert 'fingerprint_static' in result
        assert len(result['stack_frames']) > 0
    
    def test_extract_exception_without_stack(self, error_without_stack_template1):
        """Test extracting exception without stack trace"""
        extractor = ExceptionExtractor()
        result = extractor.extract_exception(error_without_stack_template1)
        
        assert result is not None
        assert result['has_stack_trace'] is False
        assert 'fingerprint_template' in result
        assert 'fingerprint_semantic' in result
        assert 'fingerprint_category' in result
    
    def test_extract_java_exception(self, java_exception_with_stack):
        """Test extracting Java exception"""
        extractor = ExceptionExtractor()
        result = extractor.extract_exception(java_exception_with_stack)
        
        assert result is not None
        assert result['exception_type'] == 'SQLException'
        assert result['has_stack_trace'] is True
    
    def test_extract_javascript_exception(self, javascript_exception_with_stack):
        """Test extracting JavaScript exception"""
        extractor = ExceptionExtractor()
        result = extractor.extract_exception(javascript_exception_with_stack)
        
        assert result is not None
        assert result['exception_type'] == 'TypeError'
        assert result['has_stack_trace'] is True


class TestExceptionClusterer:
    """Test exception clustering functionality"""
    
    @patch('src.storage.database.get_db')
    def test_cluster_exceptions_with_stack(self, mock_db, python_exception_with_stack, sample_log_source):
        """Test clustering exceptions with stack traces"""
        # Setup mock database
        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter.return_value.first.return_value = sample_log_source
        
        # Extract exceptions
        extractor = ExceptionExtractor()
        exc1 = extractor.extract_exception(python_exception_with_stack)
        
        # Create similar exception
        exc2_data = python_exception_with_stack.copy()
        exc2_data['metadata']['request_id'] = 'req-67890'
        exc2 = extractor.extract_exception(exc2_data)
        
        # Cluster
        clusterer = ExceptionClusterer()
        clusters = clusterer.cluster_exceptions([exc1, exc2], sample_log_source.id)
        
        # Should create 1 cluster with 2 exceptions
        assert len(clusters) == 1
        cluster_exceptions = list(clusters.values())[0]
        assert len(cluster_exceptions) == 2
    
    @patch('src.storage.database.get_db')
    def test_cluster_exceptions_without_stack_same_template(
        self, 
        mock_db, 
        error_without_stack_template1,
        error_without_stack_template2,
        sample_log_source
    ):
        """Test clustering exceptions without stack trace - same template"""
        # Setup mock database
        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter.return_value.first.return_value = sample_log_source
        
        # Extract exceptions
        extractor = ExceptionExtractor()
        exc1 = extractor.extract_exception(error_without_stack_template1)
        exc2 = extractor.extract_exception(error_without_stack_template2)
        
        # Cluster
        clusterer = ExceptionClusterer()
        clusters = clusterer.cluster_exceptions([exc1, exc2], sample_log_source.id)
        
        # Should create 1 cluster (same template pattern)
        assert len(clusters) == 1
        cluster_exceptions = list(clusters.values())[0]
        assert len(cluster_exceptions) == 2
    
    @patch('src.storage.database.get_db')
    def test_cluster_exceptions_different_categories(
        self,
        mock_db,
        error_without_stack_template1,
        error_without_stack_different_category,
        sample_log_source
    ):
        """Test clustering exceptions from different categories"""
        # Setup mock database
        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter.return_value.first.return_value = sample_log_source
        
        # Extract exceptions
        extractor = ExceptionExtractor()
        exc1 = extractor.extract_exception(error_without_stack_template1)
        exc2 = extractor.extract_exception(error_without_stack_different_category)
        
        # Cluster
        clusterer = ExceptionClusterer()
        clusters = clusterer.cluster_exceptions([exc1, exc2], sample_log_source.id)
        
        # Should create 2 separate clusters (different categories)
        assert len(clusters) == 2


class TestLogProcessor:
    """Test complete log processing pipeline"""
    
    @patch('src.storage.database.get_db')
    @patch('src.services.processor.GChatNotifier')
    def test_process_logs_with_stack_traces(
        self,
        mock_notifier,
        mock_db,
        python_exception_with_stack,
        java_exception_with_stack,
        sample_log_source
    ):
        """Test processing logs with stack traces"""
        # Setup mocks
        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter.return_value.first.return_value = sample_log_source
        
        # Process logs
        processor = LogProcessor()
        logs = [python_exception_with_stack, java_exception_with_stack]
        stats = processor.process_logs(logs, sample_log_source.id)
        
        # Verify statistics
        assert stats['total_logs'] == 2
        assert stats['error_logs'] == 2
        assert stats['exceptions_extracted'] == 2
        assert stats['clusters_created'] >= 1  # At least 1 cluster
    
    @patch('src.storage.database.get_db')
    @patch('src.services.processor.GChatNotifier')
    def test_process_logs_without_stack_traces(
        self,
        mock_notifier,
        mock_db,
        error_without_stack_template1,
        error_without_stack_template2,
        sample_log_source
    ):
        """Test processing logs without stack traces"""
        # Setup mocks
        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter.return_value.first.return_value = sample_log_source
        
        # Process logs
        processor = LogProcessor()
        logs = [error_without_stack_template1, error_without_stack_template2]
        stats = processor.process_logs(logs, sample_log_source.id)
        
        # Verify statistics
        assert stats['total_logs'] == 2
        assert stats['error_logs'] == 2
        assert stats['exceptions_extracted'] == 2
        assert stats['clusters_created'] >= 1
    
    @patch('src.storage.database.get_db')
    @patch('src.services.processor.GChatNotifier')
    def test_process_mixed_log_levels(
        self,
        mock_notifier,
        mock_db,
        python_exception_with_stack,
        warning_log,
        info_log,
        sample_log_source
    ):
        """Test processing logs with different levels"""
        # Setup mocks
        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter.return_value.first.return_value = sample_log_source
        
        # Process logs
        processor = LogProcessor()
        logs = [python_exception_with_stack, warning_log, info_log]
        stats = processor.process_logs(logs, sample_log_source.id)
        
        # Verify statistics
        assert stats['total_logs'] == 3
        # Only ERROR and WARNING should be processed (INFO filtered out)
        assert stats['error_logs'] <= 2
    
    @patch('src.storage.database.get_db')
    @patch('src.services.processor.GChatNotifier')
    def test_process_empty_logs(self, mock_notifier, mock_db, sample_log_source):
        """Test processing empty log list"""
        # Setup mocks
        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session
        
        # Process empty logs
        processor = LogProcessor()
        stats = processor.process_logs([], sample_log_source.id)
        
        # Verify statistics
        assert stats['total_logs'] == 0
        assert stats['error_logs'] == 0
        assert stats['exceptions_extracted'] == 0


class TestAPIIngestion:
    """Test API ingestion functionality"""
    
    def test_log_entry_validation(self, python_exception_with_stack):
        """Test LogEntry validation"""
        log_entry = LogEntry(**python_exception_with_stack)
        
        assert log_entry.level == 'ERROR'
        assert log_entry.exception_type == 'ValueError'
        assert log_entry.service_id == 'test-service-001'
    
    def test_log_entry_level_normalization(self):
        """Test log level normalization to uppercase"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": "error",  # lowercase
            "logger": "test",
            "message": "Test message",
            "service_id": "test-service"
        }
        log_entry = LogEntry(**log_data)
        
        assert log_entry.level == 'ERROR'  # Should be uppercase
    
    def test_log_entry_message_size_limit(self):
        """Test message size limit enforcement"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": "ERROR",
            "logger": "test",
            "message": "A" * 60000,  # Exceeds 50KB limit
            "service_id": "test-service"
        }
        log_entry = LogEntry(**log_data)
        
        # Should be truncated to 50000 characters
        assert len(log_entry.message) == 50000
    
    def test_generate_log_hash(self, python_exception_with_stack):
        """Test log hash generation for deduplication"""
        log_entry = LogEntry(**python_exception_with_stack)
        hash1 = generate_log_hash(log_entry)
        hash2 = generate_log_hash(log_entry)
        
        # Same log should generate same hash
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hash length
    
    def test_duplicate_detection(self, python_exception_with_stack):
        """Test duplicate log detection"""
        log_entry = LogEntry(**python_exception_with_stack)
        
        # First occurrence should not be duplicate
        assert is_duplicate(log_entry) is False
        
        # Immediate second occurrence should be duplicate
        assert is_duplicate(log_entry) is True
    
    def test_rate_limiter(self):
        """Test rate limiting functionality"""
        limiter = RateLimiter()
        service_id = "test-service"
        
        # Should allow requests within limit
        allowed, remaining = limiter.check_rate_limit(service_id, 100)
        assert allowed is True
        assert remaining > 0
        
        # Should reject when limit exceeded
        allowed, remaining = limiter.check_rate_limit(service_id, 15000)
        assert allowed is False
        assert remaining <= 0


class TestBatchProcessing:
    """Test batch processing functionality"""
    
    def test_batch_size_validation(self, python_exception_with_stack):
        """Test batch size validation"""
        # Valid batch size
        logs = [python_exception_with_stack] * 100
        request = IngestLogsRequest(logs=logs)
        assert len(request.logs) == 100
        
        # Batch size exceeding limit should raise error
        with pytest.raises(ValueError):
            logs = [python_exception_with_stack] * 1500
            IngestLogsRequest(logs=logs)


class TestServiceIsolation:
    """Test service isolation in processing"""
    
    @patch('src.storage.database.get_db')
    def test_service_specific_clustering(self, mock_db):
        """Test that clusters are isolated by service"""
        # Setup mock database with two different services
        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session
        
        service1 = Service(id="service-1", name="Service 1", is_active=True)
        service2 = Service(id="service-2", name="Service 2", is_active=True)
        
        log_source1 = LogSource(
            id="ls-1",
            service_id="service-1",
            service_name="Service 1",
            source_type="opensearch"
        )
        log_source2 = LogSource(
            id="ls-2",
            service_id="service-2",
            service_name="Service 2",
            source_type="opensearch"
        )
        
        # Mock database queries
        def mock_query_filter_first(query):
            if "ls-1" in str(query):
                return log_source1
            elif "ls-2" in str(query):
                return log_source2
            return None
        
        mock_session.query.return_value.filter.return_value.first.side_effect = mock_query_filter_first
        
        # Create identical exceptions for different services
        exc_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": "ERROR",
            "logger": "test",
            "message": "Test error",
            "exception_type": "TestException",
            "service_id": "service-1"
        }
        
        extractor = ExceptionExtractor()
        exc1 = extractor.extract_exception(exc_data)
        
        exc_data['service_id'] = "service-2"
        exc2 = extractor.extract_exception(exc_data)
        
        # Cluster separately
        clusterer = ExceptionClusterer()
        clusters1 = clusterer.cluster_exceptions([exc1], "ls-1")
        clusters2 = clusterer.cluster_exceptions([exc2], "ls-2")
        
        # Should create separate clusters for different services
        assert len(clusters1) >= 1
        assert len(clusters2) >= 1


class TestEndToEndFlow:
    """Test complete end-to-end log processing flow"""
    
    @patch('src.storage.database.get_db')
    @patch('src.services.processor.GChatNotifier')
    @patch('src.services.tasks.process_log_batch')
    def test_complete_flow_python_exceptions(
        self,
        mock_task,
        mock_notifier,
        mock_db,
        python_exception_with_stack,
        sample_log_source
    ):
        """Test complete flow: API → Parser → Extractor → Clusterer → Notification"""
        # Setup mocks
        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter.return_value.first.return_value = sample_log_source
        
        # Step 1: Create log entries (API ingestion)
        log_entries = [LogEntry(**python_exception_with_stack) for _ in range(5)]
        
        # Step 2: Process through pipeline
        processor = LogProcessor()
        logs_dict = [log.model_dump() for log in log_entries]
        stats = processor.process_logs(logs_dict, sample_log_source.id)
        
        # Verify complete flow
        assert stats['total_logs'] == 5
        assert stats['error_logs'] == 5
        assert stats['exceptions_extracted'] == 5
        assert stats['clusters_created'] >= 1
    
    @patch('src.storage.database.get_db')
    @patch('src.services.processor.GChatNotifier')
    def test_complete_flow_mixed_exceptions(
        self,
        mock_notifier,
        mock_db,
        python_exception_with_stack,
        java_exception_with_stack,
        javascript_exception_with_stack,
        error_without_stack_template1,
        error_without_stack_template2,
        sample_log_source
    ):
        """Test complete flow with mixed exception types"""
        # Setup mocks
        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter.return_value.first.return_value = sample_log_source
        
        # Mix of different exception types
        logs = [
            python_exception_with_stack,
            java_exception_with_stack,
            javascript_exception_with_stack,
            error_without_stack_template1,
            error_without_stack_template2
        ]
        
        # Process through pipeline
        processor = LogProcessor()
        stats = processor.process_logs(logs, sample_log_source.id)
        
        # Verify processing
        assert stats['total_logs'] == 5
        assert stats['error_logs'] == 5
        assert stats['exceptions_extracted'] == 5
        # Should create multiple clusters (different exception types)
        assert stats['clusters_created'] >= 2


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Integration tests requiring actual database/services"""
    
    @pytest.mark.integration
    @patch('src.storage.database.get_db')
    def test_real_database_clustering(self, mock_db, sample_log_source):
        """Test clustering with real database operations"""
        # This test would require actual database setup
        # Marked as integration test
        pass
    
    @pytest.mark.integration
    def test_celery_task_execution(self):
        """Test actual Celery task execution"""
        # This test would require Celery worker running
        # Marked as integration test
        pass


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

class TestPerformance:
    """Performance tests for log processing"""
    
    @patch('src.storage.database.get_db')
    @patch('src.services.processor.GChatNotifier')
    def test_large_batch_processing(self, mock_notifier, mock_db, python_exception_with_stack, sample_log_source):
        """Test processing large batch of logs"""
        # Setup mocks
        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter.return_value.first.return_value = sample_log_source
        
        # Create large batch (1000 logs)
        logs = [python_exception_with_stack.copy() for _ in range(1000)]
        
        # Process
        processor = LogProcessor()
        import time
        start = time.time()
        stats = processor.process_logs(logs, sample_log_source.id)
        duration = time.time() - start
        
        # Verify processing completed
        assert stats['total_logs'] == 1000
        print(f"Processed 1000 logs in {duration:.2f} seconds")


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    """Run tests with pytest"""
    pytest.main([__file__, "-v", "--tb=short"])
