# Fluent Bit Docker Compose Quick Start

## 🚀 5-Minute Setup Guide

This guide will help you quickly set up and test the Fluent Bit integration with Luffy using Docker Compose.

---

## 📋 Prerequisites

- Docker and Docker Compose installed
- At least 4GB RAM available
- Ports 8000, 2020, 5432, 6379, 6333, 9200 available

---

## 🔧 Step 1: Configure Environment Variables

Copy the example environment file and update it:

```bash
# Copy the example file
cp .env.example .env

# Generate a secure API token
python3 -c "import secrets; print('FLUENT_BIT_API_TOKEN=fb_' + secrets.token_urlsafe(32))" >> .env

# Or manually edit .env and set:
# FLUENT_BIT_API_TOKEN=your-secure-token-here
# SERVICE_ID=test-service
# SERVICE_NAME=Test Service
# ENVIRONMENT=development
```

**Minimum required in `.env`:**
```bash
FLUENT_BIT_API_TOKEN=fb_your-secure-token-here-change-me
SERVICE_ID=test-service
SERVICE_NAME=Test Service
ENVIRONMENT=development
```

---

## 🏗️ Step 2: Start All Services

Start all services with Docker Compose:

```bash
# Start all services in detached mode
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

**Services started:**
- ✅ PostgreSQL (port 5432)
- ✅ Redis (port 6379)
- ✅ Qdrant (port 6333)
- ✅ OpenSearch (port 9200)
- ✅ Luffy API (port 8000)
- ✅ Celery Worker
- ✅ Celery Beat
- ✅ Fluent Bit (port 2020)

---

## 🧪 Step 3: Verify Services

### **1. Check API Health**
```bash
curl http://localhost:8000/health
# Expected: {"status":"healthy"}
```

### **2. Check Fluent Bit Health**
```bash
curl http://localhost:2020/api/v1/health
# Expected: Fluent Bit metrics
```

### **3. Check Ingestion API Health**
```bash
curl -H "Authorization: Bearer fb_your-token-here" \
  http://localhost:8000/api/v1/ingest/health
# Expected: {"status":"healthy","timestamp":"..."}
```

---

## 📝 Step 4: Create Test Service

Create a test service in Luffy:

```bash
curl -X POST http://localhost:8000/api/v1/services \
  -H "Content-Type: application/json" \
  -d '{
    "id": "test-service",
    "name": "Test Service",
    "description": "Test service for Fluent Bit integration",
    "is_active": true
  }'
```

---

## 🧪 Step 5: Test Log Ingestion

### **Option A: Generate Test Logs**

Create a test log file that Fluent Bit will tail:

```bash
# Create logs directory if it doesn't exist
mkdir -p data/repos/zoro/logs

# Generate test error logs
cat > data/repos/zoro/logs/app.log << 'EOF'
{"timestamp":"2024-12-22T15:30:45.123Z","level":"ERROR","logger":"com.example.UserService","message":"Failed to connect to database","exception_type":"SQLException","exception_message":"Connection timeout after 30s","stack_trace":"java.sql.SQLException: Connection timeout\n  at com.example.db.ConnectionPool.getConnection(ConnectionPool.java:123)\n  at com.example.service.UserService.getUser(UserService.java:45)"}
{"timestamp":"2024-12-22T15:31:00.456Z","level":"ERROR","logger":"com.example.OrderService","message":"Null pointer exception","exception_type":"NullPointerException","exception_message":"Cannot invoke method on null object","stack_trace":"java.lang.NullPointerException: Cannot invoke method\n  at com.example.service.OrderService.processOrder(OrderService.java:78)"}
{"timestamp":"2024-12-22T15:31:15.789Z","level":"FATAL","logger":"com.example.PaymentService","message":"Payment gateway unreachable","exception_type":"IOException","exception_message":"Connection refused","stack_trace":"java.io.IOException: Connection refused\n  at com.example.payment.Gateway.connect(Gateway.java:234)"}
EOF

echo "✅ Test logs created in data/repos/zoro/logs/app.log"
```

### **Option B: Direct API Test**

Test the ingestion API directly:

```bash
# Get your token from .env
TOKEN=$(grep FLUENT_BIT_API_TOKEN .env | cut -d'=' -f2)

# Send a single test log
curl -X POST http://localhost:8000/api/v1/ingest/logs/single \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "2024-12-22T15:30:45.123Z",
    "level": "ERROR",
    "logger": "com.example.TestService",
    "message": "Test error from direct API call",
    "exception_type": "TestException",
    "exception_message": "This is a test exception",
    "stack_trace": "TestException: This is a test\n  at TestClass.testMethod(Test.java:10)",
    "service_id": "test-service",
    "environment": "development",
    "hostname": "test-host"
  }'

# Expected response:
# {
#   "status": "accepted",
#   "received_count": 1,
#   "accepted_count": 1,
#   "rejected_count": 0,
#   "task_id": "celery-task-uuid",
#   "message": "Logs queued for processing..."
# }
```

---

## 🔍 Step 6: Verify Processing

### **1. Check Fluent Bit Logs**
```bash
docker-compose logs fluent-bit | tail -20

# Look for:
# - "Fluent Bit v2.2.0 started"
# - HTTP output sending logs
# - No error messages
```

### **2. Check Celery Worker Logs**
```bash
docker-compose logs celery-worker | tail -20

# Look for:
# - "Task process_log_batch received"
# - "Processing X logs"
# - "Logs processed successfully"
```

### **3. Check Exception Clusters**
```bash
curl http://localhost:8000/api/v1/clusters?service_id=test-service

# Expected: List of exception clusters created from test logs
```

### **4. Check Dashboard Stats**
```bash
curl http://localhost:8000/api/v1/stats?service_id=test-service

# Expected: Statistics showing processed logs and clusters
```

---

## 📊 Step 7: Monitor Fluent Bit

### **Fluent Bit Metrics**
```bash
# View Fluent Bit metrics
curl http://localhost:2020/api/v1/metrics

# View Fluent Bit uptime
curl http://localhost:2020/api/v1/uptime

# View storage metrics
curl http://localhost:2020/api/v1/storage
```

### **Ingestion Metrics**
```bash
TOKEN=$(grep FLUENT_BIT_API_TOKEN .env | cut -d'=' -f2)

curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/ingest/metrics

# Expected: Ingestion statistics
```

---

## 🎯 Step 8: View Results in Frontend

If you have the frontend running:

```bash
# Start frontend (in another terminal)
cd frontend
npm install
npm run dev

# Open browser
open http://localhost:3000
```

Navigate to:
- **Dashboard:** See statistics for test-service
- **Clusters:** View exception clusters created from logs
- **Cluster Details:** See stack traces and RCA

---

## 🛠️ Troubleshooting

### **Fluent Bit Not Sending Logs**

```bash
# Check Fluent Bit logs
docker-compose logs fluent-bit

# Common issues:
# 1. Configuration file not found
docker exec luffy-fluent-bit ls -la /fluent-bit/etc/

# 2. Log files not accessible
docker exec luffy-fluent-bit ls -la /var/log/app/

# 3. API not reachable
docker exec luffy-fluent-bit curl -f http://api:8000/health
```

### **API Returning 401 Unauthorized**

```bash
# Check token in .env
grep FLUENT_BIT_API_TOKEN .env

# Check token in Fluent Bit container
docker exec luffy-fluent-bit env | grep LUFFY_API_TOKEN

# Verify token matches
TOKEN=$(grep FLUENT_BIT_API_TOKEN .env | cut -d'=' -f2)
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/ingest/health
```

### **Logs Not Being Processed**

```bash
# Check Celery worker status
docker-compose logs celery-worker | grep -i error

# Check Redis connection
docker exec luffy-redis redis-cli ping
# Expected: PONG

# Check queue depth
docker exec luffy-redis redis-cli LLEN celery
# Should show number of pending tasks

# Check database connection
docker exec luffy-postgres psql -U luffy_user -d observability -c "SELECT COUNT(*) FROM exception_clusters;"
```

### **Service Not Found Error**

```bash
# Create the service first
curl -X POST http://localhost:8000/api/v1/services \
  -H "Content-Type: application/json" \
  -d '{
    "id": "test-service",
    "name": "Test Service",
    "description": "Test service",
    "is_active": true
  }'

# Verify service exists
curl http://localhost:8000/api/v1/services/test-service
```

---

## 🧹 Cleanup

### **Stop All Services**
```bash
docker-compose down
```

### **Stop and Remove Volumes**
```bash
docker-compose down -v
```

### **Remove Test Logs**
```bash
rm -rf data/repos/zoro/logs/app.log
```

---

## 📈 Performance Testing

### **Generate High Volume Logs**

```bash
# Generate 1000 test logs
for i in {1..1000}; do
  echo "{\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)\",\"level\":\"ERROR\",\"logger\":\"TestService\",\"message\":\"Test error $i\",\"service_id\":\"test-service\"}" >> data/repos/zoro/logs/app.log
done

# Monitor processing
watch -n 1 'curl -s http://localhost:8000/api/v1/stats?service_id=test-service | jq ".logs_processed"'
```

### **Load Test Ingestion API**

```bash
# Install hey (HTTP load testing tool)
# brew install hey  # macOS
# apt-get install hey  # Ubuntu

TOKEN=$(grep FLUENT_BIT_API_TOKEN .env | cut -d'=' -f2)

# Run load test (100 requests, 10 concurrent)
hey -n 100 -c 10 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -m POST \
  -d '{"logs":[{"timestamp":"2024-12-22T15:30:45.123Z","level":"ERROR","logger":"LoadTest","message":"Load test","service_id":"test-service"}]}' \
  http://localhost:8000/api/v1/ingest/logs
```

---

## 🎉 Success Criteria

After completing all steps, you should see:

- ✅ All Docker containers running
- ✅ Fluent Bit tailing log files
- ✅ Logs being sent to Luffy API
- ✅ Celery workers processing logs
- ✅ Exception clusters created in database
- ✅ Dashboard showing statistics
- ✅ No errors in container logs

---

## 📚 Next Steps

1. **Configure for Production:**
   - Generate secure API tokens
   - Configure TLS/SSL
   - Set up proper log rotation
   - Configure monitoring and alerting

2. **Deploy to Kubernetes:**
   - See `FLUENT_BIT_INTEGRATION.md` for Kubernetes manifests
   - Use ConfigMaps for configuration
   - Use Secrets for API tokens

3. **Add More Services:**
   - Create additional services in Luffy
   - Deploy Fluent Bit per service
   - Configure service-specific filters

4. **Monitor Performance:**
   - Set up Prometheus metrics
   - Configure Grafana dashboards
   - Set up alerting rules

---

## 🆘 Getting Help

- **Documentation:** See `docs/FLUENT_BIT_INTEGRATION.md`
- **API Reference:** See `docs/FLUENT_BIT_IMPLEMENTATION_SUMMARY.md`
- **Logs:** `docker-compose logs -f [service-name]`
- **Container Shell:** `docker exec -it [container-name] /bin/sh`

---

**Happy Logging! 🎉**
