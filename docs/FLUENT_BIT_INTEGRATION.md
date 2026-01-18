# Fluent Bit Integration for Luffy

## 🎯 Overview

This document describes the integration of **Fluent Bit** as a log filtering and forwarding agent for the Luffy observability platform. Fluent Bit will filter error logs at the source and push them directly to Luffy's ingestion API, eliminating the need for periodic polling of OpenSearch/Elasticsearch.

## 📊 Current Architecture vs. New Architecture

### **BEFORE (Current - Pull Model):**
```
Application Logs → OpenSearch/Elasticsearch
                          ↓
                   [Periodic Polling]
                          ↓
                    Luffy Backend
                    (fetch_and_process_logs task)
                          ↓
                    Process & Cluster
```

**Problems:**
- ❌ Polling overhead (queries every 5-60 minutes)
- ❌ Duplicate log processing (overlapping time windows)
- ❌ Delayed exception detection (up to fetch interval)
- ❌ Resource intensive (scan operations on large indices)
- ❌ Complex time window management

### **AFTER (New - Push Model with Fluent Bit):**
```
Application Logs → Fluent Bit (Filter: ERROR/FATAL only)
                          ↓
                   [Real-time Push]
                          ↓
                    Luffy Ingestion API
                    (/api/v1/ingest/logs)
                          ↓
                    Process & Cluster
                          ↓
                   (Optional) OpenSearch
                   (for archival/search)
```

**Benefits:**
- ✅ Real-time ingestion (sub-second latency)
- ✅ No polling overhead
- ✅ No duplicate processing
- ✅ Immediate exception detection
- ✅ Reduced resource usage
- ✅ Scalable (Fluent Bit handles backpressure)

---

## 🏗️ Architecture Components

### **1. Fluent Bit Agent (Deployed with Each Service)**

**Role:** Log collection, filtering, and forwarding

**Configuration:**
```conf
[SERVICE]
    Flush        5
    Daemon       Off
    Log_Level    info
    Parsers_File parsers.conf
    HTTP_Server  On
    HTTP_Listen  0.0.0.0
    HTTP_Port    2020

# Input: Read application logs
[INPUT]
    Name              tail
    Path              /var/log/app/*.log
    Path_Key          file_path
    Tag               app.logs
    Parser            json
    DB                /var/log/fluent-bit-state.db
    Mem_Buf_Limit     50MB
    Skip_Long_Lines   On
    Refresh_Interval  10

# Filter: Only ERROR and FATAL logs
[FILTER]
    Name    grep
    Match   app.logs
    Regex   level (ERROR|FATAL|error|fatal|Error|Fatal)

# Filter: Add service metadata
[FILTER]
    Name    record_modifier
    Match   app.logs
    Record  service_id ${SERVICE_ID}
    Record  service_name ${SERVICE_NAME}
    Record  environment ${ENVIRONMENT}
    Record  hostname ${HOSTNAME}

# Filter: Parse stack traces
[FILTER]
    Name    multiline
    Match   app.logs
    multiline.key_content message
    multiline.parser java_stacktrace,python_stacktrace,nodejs_stacktrace

# Output: Send to Luffy ingestion API
[OUTPUT]
    Name              http
    Match             app.logs
    Host              luffy-api.example.com
    Port              8000
    URI               /api/v1/ingest/logs
    Format            json
    Header            Authorization Bearer ${LUFFY_API_TOKEN}
    Header            Content-Type application/json
    Retry_Limit       5
    net.keepalive     on
    net.keepalive_idle_timeout 30

# Output: Also send to OpenSearch (optional, for archival)
[OUTPUT]
    Name              opensearch
    Match             app.logs
    Host              opensearch.example.com
    Port              9200
    Index             luffy-errors
    Type              _doc
    HTTP_User         ${OPENSEARCH_USER}
    HTTP_Passwd       ${OPENSEARCH_PASSWORD}
    tls               On
    tls.verify        On
    Retry_Limit       3
```

### **2. Luffy Ingestion API (New Endpoint)**

**Endpoint:** `POST /api/v1/ingest/logs`

**Features:**
- Accepts batches of error logs from Fluent Bit
- Validates service_id and authentication
- Queues logs for async processing
- Returns immediate acknowledgment
- Handles backpressure with rate limiting

**Request Format:**
```json
{
  "logs": [
    {
      "timestamp": "2024-12-22T15:30:45.123Z",
      "level": "ERROR",
      "logger": "com.example.UserService",
      "message": "Failed to connect to database",
      "exception_type": "java.sql.SQLException",
      "exception_message": "Connection timeout after 30s",
      "stack_trace": "java.sql.SQLException: Connection timeout...\n  at com.example...",
      "service_id": "web-app",
      "service_name": "Web Application",
      "environment": "production",
      "hostname": "web-app-pod-1",
      "file_path": "/var/log/app/application.log",
      "metadata": {
        "user_id": "12345",
        "request_id": "abc-def-ghi",
        "custom_field": "value"
      }
    }
  ]
}
```

**Response:**
```json
{
  "status": "accepted",
  "received_count": 1,
  "task_id": "celery-task-uuid",
  "message": "Logs queued for processing"
}
```

### **3. Async Processing Pipeline**

**Flow:**
```
Ingestion API → Redis Queue → Celery Worker → Process Logs → Cluster → Store
```

**New Celery Task:**
```python
@celery_app.task(bind=True, name='ingest_logs_batch')
def ingest_logs_batch(self, logs: List[Dict], service_id: str):
    """
    Process a batch of logs from Fluent Bit.
    
    This task:
    1. Validates logs
    2. Normalizes format
    3. Extracts exceptions
    4. Clusters similar exceptions
    5. Triggers RCA if needed
    """
```

---

## 🔧 Implementation Plan

### **Phase 1: Backend API (Week 1)**

**Files to Create:**
1. `src/services/api_ingest.py` - New ingestion API endpoints
2. `src/ingestion/fluent_bit_parser.py` - Parse Fluent Bit log format
3. `src/services/rate_limiter.py` - Rate limiting for ingestion

**Files to Modify:**
1. `src/services/api.py` - Add ingestion router
2. `src/services/tasks.py` - Add ingest_logs_batch task
3. `src/storage/models.py` - Add IngestionMetrics model

**API Endpoints:**
- `POST /api/v1/ingest/logs` - Batch log ingestion
- `POST /api/v1/ingest/logs/single` - Single log ingestion (testing)
- `GET /api/v1/ingest/metrics` - Ingestion metrics
- `GET /api/v1/ingest/health` - Health check for Fluent Bit

**Features:**
- JWT/API token authentication
- Service-based authorization (service_id validation)
- Request validation (max batch size: 1000 logs)
- Rate limiting (per service: 10,000 logs/minute)
- Async processing via Celery
- Metrics tracking (ingestion rate, processing time)

### **Phase 2: Fluent Bit Configuration (Week 1)**

**Files to Create:**
1. `fluent-bit/fluent-bit.conf` - Main configuration
2. `fluent-bit/parsers.conf` - Log parsers
3. `fluent-bit/Dockerfile` - Custom Fluent Bit image
4. `fluent-bit/docker-compose.yml` - Testing setup
5. `docs/FLUENT_BIT_SETUP.md` - Setup guide

**Parsers:**
- JSON logs (default)
- Java stack traces (multiline)
- Python stack traces (multiline)
- Node.js stack traces (multiline)
- Custom application formats

### **Phase 3: Deployment & Testing (Week 2)**

**Kubernetes Deployment:**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: fluent-bit-config
data:
  fluent-bit.conf: |
    # Configuration here

---
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: fluent-bit
spec:
  selector:
    matchLabels:
      app: fluent-bit
  template:
    metadata:
      labels:
        app: fluent-bit
    spec:
      containers:
      - name: fluent-bit
        image: fluent/fluent-bit:2.2
        volumeMounts:
        - name: config
          mountPath: /fluent-bit/etc/
        - name: varlog
          mountPath: /var/log
        env:
        - name: SERVICE_ID
          valueFrom:
            fieldRef:
              fieldPath: metadata.labels['service']
        - name: LUFFY_API_TOKEN
          valueFrom:
            secretKeyRef:
              name: luffy-secrets
              key: api-token
      volumes:
      - name: config
        configMap:
          name: fluent-bit-config
      - name: varlog
        hostPath:
          path: /var/log
```

**Docker Compose (Testing):**
```yaml
version: '3.8'
services:
  fluent-bit:
    image: fluent/fluent-bit:2.2
    volumes:
      - ./fluent-bit/fluent-bit.conf:/fluent-bit/etc/fluent-bit.conf
      - ./fluent-bit/parsers.conf:/fluent-bit/etc/parsers.conf
      - ./logs:/var/log/app
    environment:
      - SERVICE_ID=test-service
      - SERVICE_NAME=Test Service
      - ENVIRONMENT=development
      - LUFFY_API_TOKEN=test-token
    depends_on:
      - luffy-api
```

### **Phase 4: Migration Strategy (Week 2)**

**Hybrid Approach (Recommended):**
1. **Week 1-2:** Deploy Fluent Bit alongside existing polling
2. **Week 3:** Monitor both systems, compare results
3. **Week 4:** Gradually reduce polling frequency
4. **Week 5:** Disable polling for services with Fluent Bit
5. **Week 6:** Full cutover, keep polling as fallback

**Rollback Plan:**
- Keep OpenSearch polling code intact
- Feature flag: `ENABLE_FLUENT_BIT_INGESTION`
- Can disable Fluent Bit ingestion instantly
- No data loss (logs still in OpenSearch)

---

## 🚀 Performance & Scalability

### **Throughput:**
- **Fluent Bit:** 100,000+ logs/second per instance
- **Luffy API:** 10,000 logs/second (with 4 workers)
- **Celery Workers:** 5,000 logs/second (with 10 workers)

**Bottleneck:** Celery workers (can scale horizontally)

### **Latency:**
- **Fluent Bit → API:** < 100ms
- **API → Celery Queue:** < 10ms
- **Celery Processing:** 100-500ms per batch
- **End-to-End:** < 1 second (real-time)

### **Resource Usage:**
- **Fluent Bit:** 50-100 MB RAM, < 5% CPU per instance
- **API:** 200 MB RAM, 10-20% CPU per worker
- **Celery:** 300 MB RAM, 20-40% CPU per worker

### **Scalability:**
```
1 service (1K errors/min) → 1 Fluent Bit, 1 API worker, 2 Celery workers
10 services (10K errors/min) → 10 Fluent Bit, 2 API workers, 5 Celery workers
100 services (100K errors/min) → 100 Fluent Bit, 4 API workers, 20 Celery workers
```

**Horizontal Scaling:**
- Fluent Bit: Scales with services (1 per service/pod)
- API: Scales with load (add more uvicorn workers)
- Celery: Scales with processing needs (add more workers)

---

## 🛡️ Resilience & Reliability

### **1. Backpressure Handling**

**Fluent Bit:**
- Buffering: 50 MB per instance
- Retry logic: 5 attempts with exponential backoff
- Disk buffering: Falls back to disk if memory full

**Luffy API:**
- Rate limiting: 10,000 logs/minute per service
- Queue depth monitoring: Alert if Redis queue > 100K
- Circuit breaker: Reject requests if queue too large

**Celery:**
- Task timeout: 5 minutes per batch
- Dead letter queue: Failed tasks go to DLQ
- Retry policy: 3 attempts with exponential backoff

### **2. Data Loss Prevention**

**At Fluent Bit:**
- State file: Tracks read position in log files
- Disk buffering: Persists logs if API unavailable
- Duplicate detection: Prevents re-sending same logs

**At Luffy API:**
- Idempotency: Deduplicate logs by hash
- Persistent queue: Redis with AOF persistence
- Acknowledgment: Only ACK after queuing

**At Celery:**
- Task persistence: Tasks survive worker restarts
- Result backend: Store processing results
- Monitoring: Track failed tasks

### **3. Failure Scenarios**

| Scenario | Impact | Mitigation |
|----------|--------|------------|
| Fluent Bit crash | Logs lost until restart | Kubernetes restarts pod, state file preserves position |
| API unavailable | Fluent Bit buffers logs | Disk buffering + retry, max 5 minutes buffer |
| Celery worker crash | Tasks requeued | Celery requeues unacked tasks, no data loss |
| Redis crash | Queue lost | Redis persistence (AOF), backup to disk |
| Database unavailable | Processing fails | Retry queue, exponential backoff, alert |

### **4. Monitoring & Alerting**

**Metrics to Track:**
- Fluent Bit: Logs sent, retries, buffer usage
- API: Requests/sec, latency, error rate
- Celery: Queue depth, processing time, failures
- End-to-end: Ingestion lag, processing lag

**Alerts:**
- Fluent Bit buffer > 80% → Scale API
- API error rate > 5% → Investigate
- Celery queue > 100K → Scale workers
- Processing lag > 5 minutes → Critical alert

---

## 🔄 Alternatives & Improvements

### **Alternative 1: Kafka as Message Broker**

**Architecture:**
```
Fluent Bit → Kafka → Luffy Consumer → Process
```

**Pros:**
- Higher throughput (millions of logs/sec)
- Better durability (persistent log)
- Replay capability (reprocess old logs)
- Decoupling (Luffy can be offline)

**Cons:**
- More complexity (Kafka cluster)
- Higher resource usage (Zookeeper, brokers)
- Operational overhead (Kafka management)

**Recommendation:** Use if processing > 100K logs/minute

### **Alternative 2: Direct Database Write**

**Architecture:**
```
Fluent Bit → PostgreSQL (via HTTP output) → Process
```

**Pros:**
- Simplest architecture
- No message broker needed
- Direct persistence

**Cons:**
- Database becomes bottleneck
- No async processing
- Tight coupling

**Recommendation:** NOT recommended for production

### **Alternative 3: Hybrid Push-Pull**

**Architecture:**
```
Critical Services → Fluent Bit → Luffy (Push)
Non-Critical Services → OpenSearch → Luffy (Pull)
```

**Pros:**
- Best of both worlds
- Gradual migration
- Flexibility per service

**Cons:**
- Maintains two pipelines
- More complexity

**Recommendation:** Good for migration phase

### **Improvement 1: Structured Logging**

**Enforce JSON logging across all services:**
```json
{
  "timestamp": "2024-12-22T15:30:45.123Z",
  "level": "ERROR",
  "logger": "UserService",
  "message": "Database connection failed",
  "exception": {
    "type": "SQLException",
    "message": "Connection timeout",
    "stack_trace": "..."
  },
  "context": {
    "user_id": "12345",
    "request_id": "abc-def"
  }
}
```

**Benefits:**
- Easier parsing
- Consistent format
- Better metadata extraction

### **Improvement 2: Log Sampling**

**For high-volume services:**
```conf
[FILTER]
    Name    sampling
    Match   app.logs
    Rate    10  # Keep 1 in 10 logs
```

**Benefits:**
- Reduces volume by 90%
- Still detects patterns
- Lower costs

**Use Cases:**
- Debug logs (sample heavily)
- Info logs (sample moderately)
- Error logs (never sample)

### **Improvement 3: Edge Processing**

**Pre-process logs at Fluent Bit:**
```conf
[FILTER]
    Name    lua
    Match   app.logs
    script  extract_exception.lua
    call    extract_exception
```

**Benefits:**
- Reduces API load
- Faster processing
- Lower bandwidth

---

## 📋 Implementation Checklist

### **Backend (Week 1)**
- [ ] Create `api_ingest.py` with ingestion endpoints
- [ ] Add authentication (JWT/API tokens)
- [ ] Add rate limiting (per service)
- [ ] Add request validation (batch size, format)
- [ ] Create `ingest_logs_batch` Celery task
- [ ] Add idempotency (deduplication)
- [ ] Add metrics tracking
- [ ] Write unit tests
- [ ] Write integration tests

### **Fluent Bit (Week 1)**
- [ ] Create `fluent-bit.conf` configuration
- [ ] Create `parsers.conf` for stack traces
- [ ] Create Docker image with custom config
- [ ] Test with sample logs
- [ ] Test error scenarios (API down, network issues)
- [ ] Document configuration options
- [ ] Create Kubernetes manifests

### **Deployment (Week 2)**
- [ ] Deploy Fluent Bit to staging
- [ ] Deploy API changes to staging
- [ ] Run load tests (1K, 10K, 100K logs/min)
- [ ] Monitor metrics and alerts
- [ ] Fix any issues
- [ ] Deploy to production (1 service)
- [ ] Monitor for 1 week
- [ ] Gradually roll out to all services

### **Migration (Week 2-6)**
- [ ] Week 2: Deploy Fluent Bit alongside polling
- [ ] Week 3: Compare results, validate accuracy
- [ ] Week 4: Reduce polling frequency (60min → 120min)
- [ ] Week 5: Disable polling for Fluent Bit services
- [ ] Week 6: Full cutover, keep polling as fallback

---

## 🎯 Recommended Approach

**For Luffy, I recommend:**

1. **Start with Fluent Bit + HTTP Output (Phase 1)**
   - Simplest to implement
   - Leverages existing Celery infrastructure
   - No new dependencies (Kafka, etc.)
   - Can scale to 100K logs/minute

2. **Hybrid Push-Pull During Migration**
   - Keep OpenSearch polling as fallback
   - Gradually migrate services to Fluent Bit
   - Zero downtime, zero data loss

3. **Future: Kafka for High-Volume Services**
   - If any service exceeds 100K logs/minute
   - Provides better durability and replay
   - Can be added later without breaking changes

4. **Enforce Structured Logging**
   - Require JSON logging for all services
   - Makes parsing easier and more reliable
   - Improves exception detection accuracy

---

## 📊 Expected Results

**After Implementation:**
- ✅ Real-time exception detection (< 1 second)
- ✅ 99% reduction in polling overhead
- ✅ Zero duplicate log processing
- ✅ 50% reduction in resource usage
- ✅ Better scalability (horizontal scaling)
- ✅ Improved reliability (no polling failures)
- ✅ Faster RCA generation (immediate context)

**Metrics to Track:**
- Ingestion latency: < 1 second (target)
- Processing latency: < 5 seconds (target)
- Error rate: < 0.1% (target)
- Throughput: 10,000 logs/sec (target)
- Resource usage: 50% reduction (target)

---

## 📚 References

- [Fluent Bit Documentation](https://docs.fluentbit.io/)
- [Fluent Bit HTTP Output](https://docs.fluentbit.io/manual/pipeline/outputs/http)
- [Fluent Bit Multiline Parser](https://docs.fluentbit.io/manual/pipeline/parsers/multiline)
- [FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [Celery Best Practices](https://docs.celeryproject.org/en/stable/userguide/tasks.html)
