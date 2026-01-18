# Docker Compose Fluent Bit Integration Update

## 📋 Summary

Successfully updated `docker-compose.yml` to include the new Fluent Bit container with complete integration to Luffy's ingestion API.

---

## 🔄 Changes Made

### **1. Updated Fluent Bit Service**

**BEFORE:**
```yaml
fluent-bit:
  image: fluent/fluent-bit:2.2-debug
  container_name: fluent-bit
  volumes:
    - ./fluent-bit.conf:/fluent-bit/etc/fluent-bit.conf
    - ./parsers.conf:/fluent-bit/etc/parsers.conf
    - ./data/repos/zoro/logs:/app/logs
  depends_on:
    - opensearch
  networks:
    - luffy-network
```

**AFTER:**
```yaml
# Fluent Bit - Log Collection and Forwarding
fluent-bit:
  image: fluent/fluent-bit:2.2
  container_name: luffy-fluent-bit
  ports:
    - "2020:2020"  # HTTP monitoring endpoint
  volumes:
    # Configuration files
    - ./fluent-bit/fluent-bit.conf:/fluent-bit/etc/fluent-bit.conf
    - ./fluent-bit/parsers.conf:/fluent-bit/etc/parsers.conf
    - ./fluent-bit/scripts:/fluent-bit/scripts
    # Log files to tail
    - ./data/repos/zoro/logs:/var/log/app
    # State file for tracking read position
    - fluent_bit_state:/var/log
    # Storage for buffering
    - fluent_bit_storage:/var/log/fluent-bit-storage
  environment:
    # Service identification
    SERVICE_ID: ${SERVICE_ID:-test-service}
    SERVICE_NAME: ${SERVICE_NAME:-Test Service}
    ENVIRONMENT: ${ENVIRONMENT:-development}
    HOSTNAME: ${HOSTNAME:-fluent-bit-container}
    
    # Luffy API configuration
    LUFFY_API_HOST: api
    LUFFY_API_PORT: 8000
    LUFFY_API_TOKEN: ${FLUENT_BIT_API_TOKEN:-your-secure-api-token-here}
    
    # OpenSearch configuration (optional, for archival)
    OPENSEARCH_HOST: opensearch
    OPENSEARCH_PORT: 9200
    OPENSEARCH_USER: ${OPENSEARCH_USER:-admin}
    OPENSEARCH_PASSWORD: ${OPENSEARCH_PASSWORD:-admin}
  depends_on:
    - api
    - opensearch
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:2020/api/v1/health"]
    interval: 30s
    timeout: 10s
    retries: 3
  networks:
    - luffy-network
  restart: unless-stopped
```

### **2. Added Fluent Bit Volumes**

```yaml
volumes:
  postgres_data:
  redis_data:
  qdrant_data:
  opensearch_data:
  clickhouse_data:
  fluent_bit_state:      # NEW - State file for read position tracking
  fluent_bit_storage:    # NEW - Storage for buffering
```

### **3. Added Fluent Bit Configuration to API Service**

```yaml
api:
  environment:
    # ... existing environment variables ...
    
    # Fluent Bit Ingestion API (NEW)
    FLUENT_BIT_API_TOKEN: ${FLUENT_BIT_API_TOKEN:-your-secure-api-token-here}
    FLUENT_BIT_RATE_LIMIT: ${FLUENT_BIT_RATE_LIMIT:-10000}
    FLUENT_BIT_BATCH_SIZE_LIMIT: ${FLUENT_BIT_BATCH_SIZE_LIMIT:-1000}
    FLUENT_BIT_DEDUP_WINDOW_SECONDS: ${FLUENT_BIT_DEDUP_WINDOW_SECONDS:-600}
```

---

## 📁 New Files Created

### **1. `.env.fluent-bit.example`**
- Example environment configuration
- API token setup
- Service identification
- Rate limiting configuration
- Production examples

### **2. `docs/FLUENT_BIT_DOCKER_QUICK_START.md`**
- 5-minute setup guide
- Step-by-step instructions
- Testing procedures
- Troubleshooting guide
- Performance testing examples

---

## 🎯 Key Features

### **1. Service Identification**
- `SERVICE_ID`: Identifies which service logs belong to
- `SERVICE_NAME`: Human-readable service name
- `ENVIRONMENT`: Environment (dev/staging/prod)
- `HOSTNAME`: Host/pod identifier

### **2. API Integration**
- `LUFFY_API_HOST`: Luffy API hostname (uses Docker service name)
- `LUFFY_API_PORT`: API port (8000)
- `LUFFY_API_TOKEN`: Authentication token

### **3. Monitoring**
- Port 2020 exposed for Fluent Bit metrics
- Health check endpoint
- Storage metrics available

### **4. Resilience**
- State file preserves read position across restarts
- Storage buffering for reliability
- Automatic restart on failure
- Health checks with retries

### **5. Dual Output**
- Primary: Luffy ingestion API (real-time processing)
- Secondary: OpenSearch (optional archival)

---

## 🚀 Usage

### **Quick Start**

```bash
# 1. Copy environment example
cp .env.example .env

# 2. Generate secure token
python3 -c "import secrets; print('FLUENT_BIT_API_TOKEN=fb_' + secrets.token_urlsafe(32))" >> .env

# 3. Start all services
docker-compose up -d

# 4. Check status
docker-compose ps

# 5. View logs
docker-compose logs -f fluent-bit
```

### **Test Ingestion**

```bash
# Create test logs
mkdir -p data/repos/zoro/logs
echo '{"timestamp":"2024-12-22T15:30:45.123Z","level":"ERROR","message":"Test error"}' >> data/repos/zoro/logs/app.log

# Check Fluent Bit processed it
docker-compose logs fluent-bit | grep "Test error"

# Check Luffy received it
curl http://localhost:8000/api/v1/clusters?service_id=test-service
```

---

## 🔧 Configuration

### **Required Environment Variables**

Add to `.env`:
```bash
# Minimum required
FLUENT_BIT_API_TOKEN=fb_your-secure-token-here
SERVICE_ID=test-service
SERVICE_NAME=Test Service
ENVIRONMENT=development
```

### **Optional Environment Variables**

```bash
# Rate limiting
FLUENT_BIT_RATE_LIMIT=10000
FLUENT_BIT_BATCH_SIZE_LIMIT=1000
FLUENT_BIT_DEDUP_WINDOW_SECONDS=600

# OpenSearch (for archival)
OPENSEARCH_USER=admin
OPENSEARCH_PASSWORD=admin

# Custom hostname
HOSTNAME=my-custom-hostname
```

---

## 📊 Architecture

```
Application Logs (data/repos/zoro/logs/*.log)
    ↓
Fluent Bit Container (luffy-fluent-bit)
    ├─ Filter: ERROR/FATAL only
    ├─ Parse: Multiline stack traces
    ├─ Add: Service metadata
    └─ Output:
        ├─ Primary: Luffy API (api:8000/api/v1/ingest/logs)
        └─ Secondary: OpenSearch (opensearch:9200)
    ↓
Luffy API Container (api)
    ├─ Authenticate
    ├─ Rate Limit
    ├─ Deduplicate
    └─ Queue to Redis
    ↓
Celery Worker Container (celery-worker)
    ├─ Process logs
    ├─ Extract exceptions
    ├─ Cluster similar exceptions
    └─ Store in PostgreSQL
```

---

## 🔍 Monitoring

### **Fluent Bit Metrics**
```bash
# View metrics
curl http://localhost:2020/api/v1/metrics

# View uptime
curl http://localhost:2020/api/v1/uptime

# View storage
curl http://localhost:2020/api/v1/storage
```

### **Container Health**
```bash
# Check all containers
docker-compose ps

# Check Fluent Bit health
docker inspect luffy-fluent-bit | jq '.[0].State.Health'

# View Fluent Bit logs
docker-compose logs -f fluent-bit
```

### **Ingestion Stats**
```bash
TOKEN=$(grep FLUENT_BIT_API_TOKEN .env | cut -d'=' -f2)

curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/ingest/metrics
```

---

## 🛡️ Security

### **1. API Token**
- Generate secure random token
- Store in `.env` file (not committed to git)
- Rotate regularly in production

```bash
# Generate token
python3 -c "import secrets; print('fb_' + secrets.token_urlsafe(32))"
```

### **2. Network Isolation**
- All services on private `luffy-network`
- Only API port 8000 exposed to host
- Fluent Bit port 2020 exposed for monitoring

### **3. Rate Limiting**
- 10,000 logs/minute per service (default)
- Configurable per deployment
- Prevents DoS attacks

### **4. Input Validation**
- Message size limits (50KB)
- Stack trace limits (100KB)
- Batch size limits (1000 logs)

---

## 🧪 Testing

### **1. Unit Test**
```bash
# Test API endpoint directly
TOKEN=$(grep FLUENT_BIT_API_TOKEN .env | cut -d'=' -f2)

curl -X POST http://localhost:8000/api/v1/ingest/logs/single \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "2024-12-22T15:30:45.123Z",
    "level": "ERROR",
    "logger": "TestService",
    "message": "Test error",
    "service_id": "test-service"
  }'
```

### **2. Integration Test**
```bash
# Generate test log file
echo '{"timestamp":"2024-12-22T15:30:45.123Z","level":"ERROR","message":"Integration test"}' >> data/repos/zoro/logs/app.log

# Wait 5 seconds
sleep 5

# Check if processed
curl http://localhost:8000/api/v1/clusters?service_id=test-service | jq '.clusters[] | select(.representative_message | contains("Integration test"))'
```

### **3. Load Test**
```bash
# Generate 1000 logs
for i in {1..1000}; do
  echo "{\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)\",\"level\":\"ERROR\",\"message\":\"Load test $i\",\"service_id\":\"test-service\"}" >> data/repos/zoro/logs/app.log
done

# Monitor processing
watch -n 1 'docker-compose logs celery-worker | grep "Logs processed" | tail -5'
```

---

## 🚨 Troubleshooting

### **Issue: Fluent Bit not starting**
```bash
# Check logs
docker-compose logs fluent-bit

# Common causes:
# 1. Configuration file syntax error
docker exec luffy-fluent-bit fluent-bit -c /fluent-bit/etc/fluent-bit.conf --dry-run

# 2. Missing volumes
docker inspect luffy-fluent-bit | jq '.[0].Mounts'
```

### **Issue: Logs not being sent to API**
```bash
# Check Fluent Bit can reach API
docker exec luffy-fluent-bit curl -f http://api:8000/health

# Check API token
docker exec luffy-fluent-bit env | grep LUFFY_API_TOKEN

# Check Fluent Bit output logs
docker-compose logs fluent-bit | grep -i "http"
```

### **Issue: API returning 401**
```bash
# Verify token matches
echo "Fluent Bit token:"
docker exec luffy-fluent-bit env | grep LUFFY_API_TOKEN

echo "API expects:"
grep FLUENT_BIT_API_TOKEN .env

# They should match!
```

### **Issue: High memory usage**
```bash
# Check Fluent Bit storage
curl http://localhost:2020/api/v1/storage

# Reduce buffer size in fluent-bit.conf:
# storage.max_chunks_up     64  # Reduce from 128
# storage.backlog.mem_limit 25M # Reduce from 50M
```

---

## 📈 Performance Tuning

### **1. Increase Throughput**
```bash
# In .env:
FLUENT_BIT_RATE_LIMIT=50000  # Increase from 10000
FLUENT_BIT_BATCH_SIZE_LIMIT=2000  # Increase from 1000

# Restart Fluent Bit
docker-compose restart fluent-bit
```

### **2. Reduce Latency**
```yaml
# In fluent-bit.conf:
[SERVICE]
    Flush        1  # Reduce from 5 seconds
```

### **3. Scale Workers**
```bash
# Scale Celery workers
docker-compose up -d --scale celery-worker=3
```

---

## 🎉 Success Checklist

After setup, verify:

- ✅ All containers running: `docker-compose ps`
- ✅ Fluent Bit healthy: `curl http://localhost:2020/api/v1/health`
- ✅ API healthy: `curl http://localhost:8000/health`
- ✅ Ingestion API accessible: `curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/ingest/health`
- ✅ Test logs processed: Check clusters API
- ✅ No errors in logs: `docker-compose logs | grep -i error`

---

## 📚 Additional Resources

- **Complete Guide:** `docs/FLUENT_BIT_INTEGRATION.md`
- **Quick Start:** `docs/FLUENT_BIT_DOCKER_QUICK_START.md`
- **Implementation Summary:** `docs/FLUENT_BIT_IMPLEMENTATION_SUMMARY.md`
- **Environment Example:** `.env.fluent-bit.example`

---

**Docker Compose setup complete! Ready for testing. 🚀**
