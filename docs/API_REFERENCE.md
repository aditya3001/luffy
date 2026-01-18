# API Reference

This document describes the REST API endpoints for the AI-Powered Log Observability Platform.

## Base URL

```
http://localhost:8000/api/v1
```

For production:
```
https://observability.yourcompany.com/api/v1
```

## Authentication

All API requests require authentication using JWT tokens or API keys.

### Headers

```
Authorization: Bearer <jwt_token>
# OR
X-API-Key: <api_key>
```

## Endpoints

### 1. Clusters

#### GET /clusters

Retrieve a list of exception clusters.

**Query Parameters:**
- `service` (optional): Filter by service name
- `environment` (optional): Filter by environment (prod, staging, dev)
- `level` (optional): Filter by log level (ERROR, WARN, etc.)
- `time_range` (optional): Time range in hours (default: 24)
- `status` (optional): Filter by status (new, investigating, resolved)
- `limit` (optional): Number of results (default: 50, max: 1000)
- `offset` (optional): Pagination offset (default: 0)

**Example Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/clusters?service=api-gateway&time_range=24" \
  -H "Authorization: Bearer <token>"
```

**Response:**
```json
{
  "total": 42,
  "clusters": [
    {
      "cluster_id": "cluster_001",
      "fingerprint_static": "abc123...",
      "exception_type": "NullPointerException",
      "exception_message": "Cannot invoke method on null object",
      "service": "api-gateway",
      "version": "v1.2.3",
      "count_24h": 156,
      "first_seen": "2025-10-11T10:30:00Z",
      "last_seen": "2025-10-12T08:15:00Z",
      "status": "new",
      "has_rca": true
    }
  ]
}
```

---

#### GET /clusters/{cluster_id}

Get detailed information about a specific cluster.

**Path Parameters:**
- `cluster_id` (required): Cluster identifier

**Example Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/clusters/cluster_001" \
  -H "Authorization: Bearer <token>"
```

**Response:**
```json
{
  "cluster_id": "cluster_001",
  "fingerprint_static": "abc123...",
  "exception_type": "NullPointerException",
  "exception_message": "Cannot invoke method on null object",
  "service": "api-gateway",
  "version": "v1.2.3",
  "count_24h": 156,
  "first_seen": "2025-10-11T10:30:00Z",
  "last_seen": "2025-10-12T08:15:00Z",
  "status": "new",
  "representative_exception": {
    "timestamp": "2025-10-12T08:15:00Z",
    "trace_id": "trace_xyz789",
    "request_id": "req_001",
    "stack_frames": [
      {
        "file": "src/handlers/user.py",
        "function": "get_user_by_id",
        "line": 145,
        "code_context": "user = database.query(user_id)"
      },
      {
        "file": "src/database/query.py",
        "function": "query",
        "line": 89,
        "code_context": "return self.execute(query)"
      }
    ],
    "extracted_parameters": {
      "user_id": "12345",
      "request_path": "/api/users/12345",
      "method": "GET"
    }
  },
  "timeline": [
    {
      "timestamp": "2025-10-12T08:00:00Z",
      "count": 12
    },
    {
      "timestamp": "2025-10-12T09:00:00Z",
      "count": 24
    }
  ]
}
```

---

### 2. Root Cause Analysis (RCA)

#### GET /rca/{cluster_id}

Get the RCA for a specific cluster.

**Path Parameters:**
- `cluster_id` (required): Cluster identifier

**Example Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/rca/cluster_001" \
  -H "Authorization: Bearer <token>"
```

**Response:**
```json
{
  "rca_id": "rca_001",
  "cluster_id": "cluster_001",
  "version": "v1.2.3",
  "commit_sha": "abc123def456",
  "created_at": "2025-10-12T08:20:00Z",
  "likely_root_cause": {
    "file_path": "src/handlers/user.py",
    "symbol": "get_user_by_id",
    "line_range": [142, 145],
    "confidence": 0.92,
    "reasoning": "The function calls database.query() without checking if the result is None. When the user_id doesn't exist in the database, query() returns None, causing a NullPointerException on the next line when trying to access methods on the None object."
  },
  "involved_parameters": [
    {
      "name": "user_id",
      "value": "12345",
      "why_relevant": "This user ID does not exist in the database, causing query() to return None"
    }
  ],
  "fix_suggestions": [
    "Add a null check after database.query() call",
    "Return a 404 error when user is not found instead of allowing None propagation",
    "Add validation for user_id format before database query"
  ],
  "tests_to_add": [
    "Test get_user_by_id with non-existent user_id",
    "Test get_user_by_id with invalid user_id format",
    "Test error handling when database returns None"
  ],
  "code_snippet": "def get_user_by_id(user_id):\n    user_data = database.query(user_id)\n    if user_data is None:\n        raise UserNotFoundException(user_id)\n    return User.from_dict(user_data)",
  "user_feedback_summary": {
    "total_votes": 15,
    "accepted": 13,
    "rejected": 2,
    "acceptance_rate": 0.87
  }
}
```

---

#### POST /rca/regenerate/{cluster_id}

Request regeneration of RCA for a cluster.

**Path Parameters:**
- `cluster_id` (required): Cluster identifier

**Request Body:**
```json
{
  "reason": "Previous RCA was incorrect",
  "additional_context": "Consider the recent database migration"
}
```

**Response:**
```json
{
  "status": "queued",
  "job_id": "job_12345",
  "estimated_completion": "2025-10-12T08:25:00Z"
}
```

---

### 3. Code

#### GET /code/{file_path}

Retrieve code snippet for a specific file.

**Path Parameters:**
- `file_path` (required): URL-encoded file path

**Query Parameters:**
- `version` (optional): Code version/commit SHA
- `start_line` (optional): Starting line number
- `end_line` (optional): Ending line number

**Example Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/code/src%2Fhandlers%2Fuser.py?start_line=140&end_line=155" \
  -H "Authorization: Bearer <token>"
```

**Response:**
```json
{
  "file_path": "src/handlers/user.py",
  "version": "v1.2.3",
  "commit_sha": "abc123def456",
  "start_line": 140,
  "end_line": 155,
  "code": "def get_user_by_id(user_id):\n    \"\"\"Retrieve user by ID from database\"\"\"\n    user_data = database.query(user_id)\n    return User.from_dict(user_data)",
  "language": "python"
}
```

---

### 4. Search

#### GET /search

Search logs and exceptions.

**Query Parameters:**
- `query` (required): Search query string
- `service` (optional): Filter by service
- `level` (optional): Filter by log level
- `time_range` (optional): Time range in hours (default: 24)
- `limit` (optional): Number of results (default: 50)

**Example Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/search?query=NullPointerException&service=api-gateway" \
  -H "Authorization: Bearer <token>"
```

**Response:**
```json
{
  "total": 234,
  "results": [
    {
      "type": "exception",
      "cluster_id": "cluster_001",
      "exception_type": "NullPointerException",
      "message": "Cannot invoke method on null object",
      "timestamp": "2025-10-12T08:15:00Z",
      "service": "api-gateway",
      "relevance_score": 0.95
    },
    {
      "type": "log",
      "log_id": "log_456",
      "message": "Processing request for user 12345",
      "timestamp": "2025-10-12T08:14:59Z",
      "service": "api-gateway",
      "relevance_score": 0.78
    }
  ]
}
```

---

### 5. Feedback

#### POST /feedback

Submit feedback on an RCA result.

**Request Body:**
```json
{
  "rca_id": "rca_001",
  "verdict": "accept",
  "notes": "Accurate analysis, fixed the issue as suggested",
  "actual_root_cause": null
}
```

**Verdict Options:**
- `accept`: RCA was accurate
- `reject`: RCA was incorrect
- `partially_correct`: RCA was partially correct

**Response:**
```json
{
  "feedback_id": "feedback_789",
  "status": "recorded",
  "message": "Thank you for your feedback"
}
```

---

#### GET /feedback/stats/{cluster_id}

Get feedback statistics for a cluster's RCA.

**Path Parameters:**
- `cluster_id` (required): Cluster identifier

**Response:**
```json
{
  "cluster_id": "cluster_001",
  "total_feedback": 15,
  "accepted": 13,
  "rejected": 2,
  "partially_correct": 0,
  "acceptance_rate": 0.87,
  "recent_feedback": [
    {
      "feedback_id": "feedback_789",
      "verdict": "accept",
      "notes": "Accurate analysis",
      "created_at": "2025-10-12T09:00:00Z",
      "user": "john.doe"
    }
  ]
}
```

---

### 6. Services

#### GET /services

List all monitored services.

**Response:**
```json
{
  "services": [
    {
      "name": "api-gateway",
      "environment": "production",
      "version": "v1.2.3",
      "health_status": "healthy",
      "exception_count_24h": 42,
      "last_deployment": "2025-10-10T14:30:00Z"
    },
    {
      "name": "user-service",
      "environment": "production",
      "version": "v2.1.0",
      "health_status": "degraded",
      "exception_count_24h": 156,
      "last_deployment": "2025-10-11T10:00:00Z"
    }
  ]
}
```

---

### 7. Statistics

#### GET /stats/overview

Get system-wide statistics.

**Query Parameters:**
- `time_range` (optional): Time range in hours (default: 24)

**Response:**
```json
{
  "time_range_hours": 24,
  "total_exceptions": 1234,
  "unique_clusters": 42,
  "services_affected": 8,
  "rca_generated": 38,
  "rca_acceptance_rate": 0.85,
  "top_services_by_exceptions": [
    {
      "service": "api-gateway",
      "count": 456
    },
    {
      "service": "user-service",
      "count": 234
    }
  ],
  "trend": "increasing"
}
```

---

## Webhooks

### Webhook Configuration

Configure webhooks to receive notifications for new clusters or RCA results.

#### POST /webhooks

Create a webhook.

**Request Body:**
```json
{
  "url": "https://your-app.com/webhook",
  "events": ["cluster.created", "rca.completed"],
  "filters": {
    "service": "api-gateway",
    "min_confidence": 0.8
  }
}
```

**Response:**
```json
{
  "webhook_id": "webhook_123",
  "status": "active",
  "secret": "whsec_abc123..."
}
```

### Webhook Payload Example

```json
{
  "event": "rca.completed",
  "timestamp": "2025-10-12T08:20:00Z",
  "data": {
    "rca_id": "rca_001",
    "cluster_id": "cluster_001",
    "service": "api-gateway",
    "confidence": 0.92,
    "summary": "NullPointerException in get_user_by_id due to missing null check"
  }
}
```

---

## Error Responses

All endpoints return standard HTTP status codes and error messages.

### Error Format

```json
{
  "error": {
    "code": "CLUSTER_NOT_FOUND",
    "message": "Cluster with ID cluster_001 not found",
    "details": {}
  }
}
```

### Common Status Codes

- `200 OK`: Successful request
- `201 Created`: Resource created successfully
- `400 Bad Request`: Invalid request parameters
- `401 Unauthorized`: Missing or invalid authentication
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

---

## Rate Limiting

API requests are rate-limited to prevent abuse.

**Limits:**
- Authenticated users: 1000 requests/hour
- API keys: 5000 requests/hour

**Rate Limit Headers:**
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 856
X-RateLimit-Reset: 1697123456
```

---

## Pagination

Endpoints that return lists support pagination using `limit` and `offset` parameters.

**Example:**
```bash
# Get first 50 results
GET /clusters?limit=50&offset=0

# Get next 50 results
GET /clusters?limit=50&offset=50
```

**Response includes pagination metadata:**
```json
{
  "total": 234,
  "limit": 50,
  "offset": 0,
  "results": [...]
}
```

---

## SDK Examples

### Python

```python
import requests

class ObservabilityClient:
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.headers = {"X-API-Key": api_key}
    
    def get_clusters(self, service=None, time_range=24):
        params = {"time_range": time_range}
        if service:
            params["service"] = service
        
        response = requests.get(
            f"{self.base_url}/clusters",
            headers=self.headers,
            params=params
        )
        return response.json()
    
    def get_rca(self, cluster_id):
        response = requests.get(
            f"{self.base_url}/rca/{cluster_id}",
            headers=self.headers
        )
        return response.json()

# Usage
client = ObservabilityClient("http://localhost:8000/api/v1", "your-api-key")
clusters = client.get_clusters(service="api-gateway")
rca = client.get_rca("cluster_001")
```

### JavaScript/TypeScript

```typescript
class ObservabilityClient {
  constructor(private baseUrl: string, private apiKey: string) {}
  
  async getClusters(service?: string, timeRange: number = 24) {
    const params = new URLSearchParams({ time_range: String(timeRange) });
    if (service) params.append('service', service);
    
    const response = await fetch(
      `${this.baseUrl}/clusters?${params}`,
      {
        headers: { 'X-API-Key': this.apiKey }
      }
    );
    return response.json();
  }
  
  async getRCA(clusterId: string) {
    const response = await fetch(
      `${this.baseUrl}/rca/${clusterId}`,
      {
        headers: { 'X-API-Key': this.apiKey }
      }
    );
    return response.json();
  }
}

// Usage
const client = new ObservabilityClient('http://localhost:8000/api/v1', 'your-api-key');
const clusters = await client.getClusters('api-gateway');
const rca = await client.getRCA('cluster_001');
```

---

## API Versioning

The API uses URL-based versioning (e.g., `/api/v1/`). Breaking changes will result in a new version (e.g., `/api/v2/`).

Current version: **v1**

---

## Support

For API support, please:
- Check the documentation at `/docs`
- Open an issue on GitHub
- Contact support@yourcompany.com
