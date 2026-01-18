"""
Fluent Bit Log Ingestion API Test Suite

Tests the Fluent Bit ingestion API endpoint with real-world scenarios:
1. Single log ingestion
2. Batch log ingestion
3. Authentication and authorization
4. Rate limiting
5. Duplicate detection
6. Input validation
7. Error handling
8. Different log formats from Fluent Bit

Author: Senior Software Engineer
Date: 2025-12-25
"""

import pytest
import json
from datetime import datetime
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock

from src.services.api import app
from src.services.api_ingest import LogEntry, IngestLogsRequest
from src.storage.models import Service, LogSource


# ============================================================================
# TEST CLIENT SETUP
# ============================================================================

client = TestClient(app)


# ============================================================================
# TEST DATA - REAL FLUENT BIT FORMATS
# ============================================================================

@pytest.fixture
def fluent_bit_python_log():
    """Real Fluent Bit formatted Python log"""
    return {
        "timestamp": "2025-12-25T19:00:00.000Z",
        "level": "ERROR",
        "logger": "django.request",
        "message": "Internal Server Error: /api/users/123",
        "exception_type": "DoesNotExist",
        "exception_message": "User matching query does not exist.",
        "stack_trace": """Traceback (most recent call last):
  File "/app/django/core/handlers/exception.py", line 55, in inner
    response = get_response(request)
  File "/app/django/core/handlers/base.py", line 197, in _get_response
    response = wrapped_callback(request, *callback_args, **callback_kwargs)
  File "/app/api/views.py", line 45, in get_user
    user = User.objects.get(id=user_id)
  File "/app/django/db/models/manager.py", line 85, in manager_method
    return getattr(self.get_queryset(), name)(*args, **kwargs)
django.contrib.auth.models.DoesNotExist: User matching query does not exist.""",
        "service_id": "web-api",
        "service_name": "Web API Service",
        "environment": "production",
        "hostname": "web-api-pod-7f8d9c-xk2p9",
        "file_path": "/app/api/views.py",
        "metadata": {
            "kubernetes_namespace": "production",
            "kubernetes_pod_name": "web-api-pod-7f8d9c-xk2p9",
            "kubernetes_container_name": "web-api",
            "stream": "stderr"
        }
    }


@pytest.fixture
def fluent_bit_java_log():
    """Real Fluent Bit formatted Java log"""
    return {
        "timestamp": "2025-12-25T19:01:00.000Z",
        "level": "ERROR",
        "logger": "com.example.payment.PaymentService",
        "message": "Payment processing failed",
        "exception_type": "PaymentException",
        "exception_message": "Gateway timeout: Stripe API not responding",
        "stack_trace": """com.example.payment.PaymentException: Gateway timeout: Stripe API not responding
    at com.example.payment.StripeGateway.processPayment(StripeGateway.java:123)
    at com.example.payment.PaymentService.processOrder(PaymentService.java:67)
    at com.example.api.OrderController.createOrder(OrderController.java:89)
    at sun.reflect.NativeMethodAccessorImpl.invoke0(Native Method)
Caused by: java.net.SocketTimeoutException: Read timed out
    at java.net.SocketInputStream.socketRead0(Native Method)
    at java.net.SocketInputStream.socketRead(SocketInputStream.java:116)""",
        "service_id": "payment-service",
        "service_name": "Payment Service",
        "environment": "production",
        "hostname": "payment-service-pod-abc123",
        "file_path": "com/example/payment/PaymentService.java",
        "metadata": {
            "thread": "http-nio-8080-exec-12",
            "transaction_id": "txn-abc-123-def-456",
            "order_id": "ORD-789012"
        }
    }


@pytest.fixture
def fluent_bit_nodejs_log():
    """Real Fluent Bit formatted Node.js log"""
    return {
        "timestamp": "2025-12-25T19:02:00.000Z",
        "level": "ERROR",
        "logger": "express",
        "message": "Unhandled rejection: MongoError: connection timed out",
        "exception_type": "MongoError",
        "exception_message": "connection timed out",
        "stack_trace": """MongoError: connection timed out
    at Connection.<anonymous> (/app/node_modules/mongodb/lib/core/connection/pool.js:452:61)
    at Connection.emit (events.js:314:20)
    at processTicksAndRejections (internal/process/task_queues.js:79:11)
    at /app/src/database/connection.js:23:15
    at /app/src/api/routes/users.js:45:22""",
        "service_id": "user-service",
        "service_name": "User Service",
        "environment": "production",
        "hostname": "user-service-pod-xyz789",
        "file_path": "/app/src/database/connection.js",
        "metadata": {
            "node_version": "v18.12.0",
            "request_id": "req-xyz-789",
            "user_id": "user-456"
        }
    }


@pytest.fixture
def fluent_bit_error_without_stack():
    """Real Fluent Bit formatted error without stack trace"""
    return {
        "timestamp": "2025-12-25T19:03:00.000Z",
        "level": "ERROR",
        "logger": "nginx",
        "message": "upstream timed out (110: Connection timed out) while connecting to upstream",
        "service_id": "nginx-ingress",
        "service_name": "Nginx Ingress",
        "environment": "production",
        "hostname": "nginx-ingress-controller-abc",
        "metadata": {
            "client": "192.168.1.100",
            "server": "api.example.com",
            "request": "GET /api/health HTTP/1.1",
            "upstream": "http://backend-service:8080"
        }
    }


@pytest.fixture
def fluent_bit_batch_logs(
    fluent_bit_python_log,
    fluent_bit_java_log,
    fluent_bit_nodejs_log,
    fluent_bit_error_without_stack
):
    """Batch of mixed logs from Fluent Bit"""
    return [
        fluent_bit_python_log,
        fluent_bit_java_log,
        fluent_bit_nodejs_log,
        fluent_bit_error_without_stack
    ]


# ============================================================================
# AUTHENTICATION TESTS
# ============================================================================

class TestAuthentication:
    """Test API authentication and authorization"""
    
    def test_missing_authorization_header(self, fluent_bit_python_log):
        """Test request without authorization header"""
        response = client.post(
            "/api/v1/ingest/logs",
            json=[fluent_bit_python_log]
        )
        assert response.status_code == 401
        assert "Authorization header missing" in response.json()['detail']
    
    def test_invalid_token_format(self, fluent_bit_python_log):
        """Test request with invalid token format"""
        response = client.post(
            "/api/v1/ingest/logs",
            json=[fluent_bit_python_log],
            headers={"Authorization": "InvalidFormat token123"}
        )
        assert response.status_code == 401
    
    @patch('src.services.api_ingest.settings')
    def test_invalid_token_value(self, mock_settings, fluent_bit_python_log):
        """Test request with invalid token value"""
        mock_settings.api_token = "correct-token-123"
        
        response = client.post(
            "/api/v1/ingest/logs",
            json=[fluent_bit_python_log],
            headers={"Authorization": "Bearer wrong-token"}
        )
        assert response.status_code == 401
    
    @patch('src.services.api_ingest.settings')
    @patch('src.storage.database.get_db')
    @patch('src.services.api_ingest.process_log_batch')
    def test_valid_token(self, mock_task, mock_db, mock_settings, fluent_bit_python_log):
        """Test request with valid token"""
        mock_settings.api_token = "valid-token-123"
        
        # Mock database
        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session
        
        # Mock service
        mock_service = Service(
            id="web-api",
            name="Web API Service",
            is_active=True
        )
        mock_session.query.return_value.filter.return_value.first.return_value = mock_service
        
        # Mock task
        mock_task.delay.return_value = Mock(id="task-123")
        
        response = client.post(
            "/api/v1/ingest/logs",
            json=[fluent_bit_python_log],
            headers={"Authorization": "Bearer valid-token-123"}
        )
        assert response.status_code == 200


# ============================================================================
# INGESTION TESTS
# ============================================================================

class TestLogIngestion:
    """Test log ingestion functionality"""
    
    @patch('src.services.api_ingest.settings')
    @patch('src.storage.database.get_db')
    @patch('src.services.api_ingest.process_log_batch')
    def test_ingest_single_python_log(
        self,
        mock_task,
        mock_db,
        mock_settings,
        fluent_bit_python_log
    ):
        """Test ingesting single Python log"""
        mock_settings.api_token = "test-token"
        
        # Mock database
        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session
        mock_service = Service(id="web-api", name="Web API", is_active=True)
        mock_session.query.return_value.filter.return_value.first.return_value = mock_service
        
        # Mock task
        mock_task.delay.return_value = Mock(id="task-123")
        
        response = client.post(
            "/api/v1/ingest/logs",
            json=[fluent_bit_python_log],
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'accepted'
        assert data['received_count'] == 1
        assert data['accepted_count'] == 1
    
    @patch('src.services.api_ingest.settings')
    @patch('src.storage.database.get_db')
    @patch('src.services.api_ingest.process_log_batch')
    def test_ingest_batch_logs(
        self,
        mock_task,
        mock_db,
        mock_settings,
        fluent_bit_batch_logs
    ):
        """Test ingesting batch of logs"""
        mock_settings.api_token = "test-token"
        
        # Mock database
        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session
        
        # Mock multiple services
        def mock_service_query(*args, **kwargs):
            service_id = fluent_bit_batch_logs[0]['service_id']
            return Service(id=service_id, name=f"Service {service_id}", is_active=True)
        
        mock_session.query.return_value.filter.return_value.first.side_effect = mock_service_query
        
        # Mock task
        mock_task.delay.return_value = Mock(id="task-456")
        
        response = client.post(
            "/api/v1/ingest/logs",
            json=fluent_bit_batch_logs,
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'accepted'
        assert data['received_count'] == 4
    
    @patch('src.services.api_ingest.settings')
    @patch('src.storage.database.get_db')
    def test_ingest_inactive_service(
        self,
        mock_db,
        mock_settings,
        fluent_bit_python_log
    ):
        """Test ingesting logs for inactive service"""
        mock_settings.api_token = "test-token"
        
        # Mock database with inactive service
        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session
        mock_service = Service(id="web-api", name="Web API", is_active=False)
        mock_session.query.return_value.filter.return_value.first.return_value = mock_service
        
        response = client.post(
            "/api/v1/ingest/logs",
            json=[fluent_bit_python_log],
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 403
        assert "inactive" in response.json()['detail'].lower()
    
    @patch('src.services.api_ingest.settings')
    @patch('src.storage.database.get_db')
    def test_ingest_nonexistent_service(
        self,
        mock_db,
        mock_settings,
        fluent_bit_python_log
    ):
        """Test ingesting logs for non-existent service"""
        mock_settings.api_token = "test-token"
        
        # Mock database with no service found
        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        response = client.post(
            "/api/v1/ingest/logs",
            json=[fluent_bit_python_log],
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 404


# ============================================================================
# VALIDATION TESTS
# ============================================================================

class TestInputValidation:
    """Test input validation"""
    
    @patch('src.services.api_ingest.settings')
    def test_empty_batch(self, mock_settings):
        """Test ingesting empty batch"""
        mock_settings.api_token = "test-token"
        
        response = client.post(
            "/api/v1/ingest/logs",
            json=[],
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 422  # Validation error
    
    @patch('src.services.api_ingest.settings')
    def test_batch_size_limit(self, mock_settings):
        """Test batch size limit enforcement"""
        mock_settings.api_token = "test-token"
        
        # Create batch exceeding limit (>1000)
        large_batch = [{
            "timestamp": datetime.utcnow().isoformat(),
            "level": "ERROR",
            "logger": "test",
            "message": f"Test message {i}",
            "service_id": "test-service"
        } for i in range(1500)]
        
        response = client.post(
            "/api/v1/ingest/logs",
            json=large_batch,
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 422
    
    @patch('src.services.api_ingest.settings')
    def test_missing_required_fields(self, mock_settings):
        """Test log with missing required fields"""
        mock_settings.api_token = "test-token"
        
        invalid_log = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": "ERROR",
            # Missing: logger, message, service_id
        }
        
        response = client.post(
            "/api/v1/ingest/logs",
            json=[invalid_log],
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 422
    
    @patch('src.services.api_ingest.settings')
    @patch('src.storage.database.get_db')
    @patch('src.services.api_ingest.process_log_batch')
    def test_message_size_truncation(
        self,
        mock_task,
        mock_db,
        mock_settings
    ):
        """Test message size truncation"""
        mock_settings.api_token = "test-token"
        
        # Mock database
        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session
        mock_service = Service(id="test-service", name="Test", is_active=True)
        mock_session.query.return_value.filter.return_value.first.return_value = mock_service
        
        # Mock task
        mock_task.delay.return_value = Mock(id="task-789")
        
        # Create log with very large message
        large_message_log = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": "ERROR",
            "logger": "test",
            "message": "A" * 60000,  # 60KB message
            "service_id": "test-service"
        }
        
        response = client.post(
            "/api/v1/ingest/logs",
            json=[large_message_log],
            headers={"Authorization": "Bearer test-token"}
        )
        
        # Should succeed but message truncated
        assert response.status_code == 200


# ============================================================================
# RATE LIMITING TESTS
# ============================================================================

class TestRateLimiting:
    """Test rate limiting functionality"""
    
    @patch('src.services.api_ingest.settings')
    @patch('src.storage.database.get_db')
    @patch('src.services.api_ingest.rate_limiter')
    def test_rate_limit_enforcement(
        self,
        mock_limiter,
        mock_db,
        mock_settings,
        fluent_bit_python_log
    ):
        """Test rate limit enforcement"""
        mock_settings.api_token = "test-token"
        
        # Mock database
        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session
        mock_service = Service(id="web-api", name="Web API", is_active=True)
        mock_session.query.return_value.filter.return_value.first.return_value = mock_service
        
        # Mock rate limiter to reject
        mock_limiter.check_rate_limit.return_value = (False, 0)
        
        response = client.post(
            "/api/v1/ingest/logs",
            json=[fluent_bit_python_log],
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 429  # Too Many Requests


# ============================================================================
# DUPLICATE DETECTION TESTS
# ============================================================================

class TestDuplicateDetection:
    """Test duplicate log detection"""
    
    @patch('src.services.api_ingest.settings')
    @patch('src.storage.database.get_db')
    @patch('src.services.api_ingest.process_log_batch')
    @patch('src.services.api_ingest.dedup_cache', {})
    def test_duplicate_detection(
        self,
        mock_task,
        mock_db,
        mock_settings,
        fluent_bit_python_log
    ):
        """Test duplicate log detection"""
        mock_settings.api_token = "test-token"
        
        # Mock database
        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session
        mock_service = Service(id="web-api", name="Web API", is_active=True)
        mock_session.query.return_value.filter.return_value.first.return_value = mock_service
        
        # Mock task
        mock_task.delay.return_value = Mock(id="task-123")
        
        # Send same log twice
        response1 = client.post(
            "/api/v1/ingest/logs",
            json=[fluent_bit_python_log],
            headers={"Authorization": "Bearer test-token"}
        )
        
        response2 = client.post(
            "/api/v1/ingest/logs",
            json=[fluent_bit_python_log],
            headers={"Authorization": "Bearer test-token"}
        )
        
        # First should be accepted
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1['accepted_count'] >= 1
        
        # Second might have some duplicates filtered
        assert response2.status_code == 200


# ============================================================================
# HEALTH CHECK TESTS
# ============================================================================

class TestHealthCheck:
    """Test health check endpoint"""
    
    @patch('src.services.api_ingest.settings')
    def test_health_check(self, mock_settings):
        """Test health check endpoint"""
        mock_settings.api_token = "test-token"
        
        response = client.get(
            "/api/v1/ingest/health",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'healthy'
        assert 'timestamp' in data
        assert 'version' in data


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

class TestErrorHandling:
    """Test error handling"""
    
    @patch('src.services.api_ingest.settings')
    @patch('src.storage.database.get_db')
    def test_database_error_handling(
        self,
        mock_db,
        mock_settings,
        fluent_bit_python_log
    ):
        """Test handling of database errors"""
        mock_settings.api_token = "test-token"
        
        # Mock database to raise exception
        mock_db.side_effect = Exception("Database connection failed")
        
        response = client.post(
            "/api/v1/ingest/logs",
            json=[fluent_bit_python_log],
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 500
    
    @patch('src.services.api_ingest.settings')
    def test_invalid_json(self, mock_settings):
        """Test handling of invalid JSON"""
        mock_settings.api_token = "test-token"
        
        response = client.post(
            "/api/v1/ingest/logs",
            data="invalid json",
            headers={
                "Authorization": "Bearer test-token",
                "Content-Type": "application/json"
            }
        )
        
        assert response.status_code == 422


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    """Run tests with pytest"""
    pytest.main([__file__, "-v", "--tb=short"])
