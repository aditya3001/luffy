# Luffy Platform - User Guide

## 🎯 For Application Developers

This guide shows you how to integrate Luffy into your application to automatically track and analyze exceptions.

---

## 📦 Step 1: Deploy Luffy Platform

### One-Command Deployment

```bash
curl -fsSL https://raw.githubusercontent.com/your-org/luffy/main/deploy.sh | bash
```

**Or using Docker Compose:**

```bash
# Create directory
mkdir ~/luffy-platform && cd ~/luffy-platform

# Download docker-compose.yml
curl -O https://raw.githubusercontent.com/your-org/luffy/main/docker-compose.simple.yml

# Start
docker-compose -f docker-compose.simple.yml up -d
```

**Verify it's running:**

```bash
curl http://localhost:8000/health
# Should return: {"status":"healthy"}
```

---

## 🔧 Step 2: Add Fluent Bit to Your Application

Fluent Bit will ship your logs to Luffy for processing.

### Option A: Docker Compose (Recommended)

Add Fluent Bit to your application's `docker-compose.yml`:

```yaml
version: '3.8'

services:
  # Your application
  myapp:
    image: myapp:latest
    ports:
      - "8080:8080"
    volumes:
      - ./logs:/var/log/myapp
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  # Fluent Bit log shipper
  fluent-bit:
    image: fluent/fluent-bit:latest
    volumes:
      - ./fluent-bit.conf:/fluent-bit/etc/fluent-bit.conf:ro
      - ./logs:/var/log/myapp:ro
    depends_on:
      - myapp
    restart: unless-stopped
```

### Option B: Kubernetes

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: fluent-bit-config
data:
  fluent-bit.conf: |
    [SERVICE]
        Flush        5
        Log_Level    info

    [INPUT]
        Name         tail
        Path         /var/log/containers/*myapp*.log
        Parser       docker
        Tag          myapp

    [FILTER]
        Name         modify
        Match        *
        Add          service_id myapp
        Add          service_name My Application

    [OUTPUT]
        Name         http
        Match        *
        Host         luffy-api.default.svc.cluster.local
        Port         8000
        URI          /api/v1/ingest/logs
        Format       json

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
        image: fluent/fluent-bit:latest
        volumeMounts:
        - name: config
          mountPath: /fluent-bit/etc/
        - name: varlog
          mountPath: /var/log
          readOnly: true
      volumes:
      - name: config
        configMap:
          name: fluent-bit-config
      - name: varlog
        hostPath:
          path: /var/log
```

---

## 📝 Step 3: Configure Fluent Bit

Create `fluent-bit.conf` in your application directory:

### Basic Configuration

```ini
[SERVICE]
    Flush        5
    Daemon       Off
    Log_Level    info

[INPUT]
    Name         tail
    Path         /var/log/myapp/*.log
    Parser       json
    Tag          myapp.logs
    Refresh_Interval 5

[FILTER]
    Name         modify
    Match        *
    Add          service_id myapp
    Add          service_name My Application
    Add          environment production

[OUTPUT]
    Name         http
    Match        *
    Host         localhost
    Port         8000
    URI          /api/v1/ingest/logs
    Format       json
    json_date_key timestamp
    json_date_format iso8601
    Retry_Limit  5
```

### Advanced Configuration (with Exception Extraction)

```ini
[SERVICE]
    Flush        5
    Daemon       Off
    Log_Level    info
    Parsers_File parsers.conf

[INPUT]
    Name         tail
    Path         /var/log/myapp/*.log
    Parser       json
    Tag          myapp.logs
    Refresh_Interval 5
    Mem_Buf_Limit 5MB

[FILTER]
    # Add service metadata
    Name         modify
    Match        *
    Add          service_id myapp
    Add          service_name My Application
    Add          environment production
    Add          hostname ${HOSTNAME}

[FILTER]
    # Extract exception details using Lua
    Name         lua
    Match        *
    script       extract_exception.lua
    call         extract_exception

[FILTER]
    # Only send ERROR and FATAL logs
    Name         grep
    Match        *
    Regex        level (ERROR|FATAL|CRITICAL)

[OUTPUT]
    Name         http
    Match        *
    Host         luffy-api
    Port         8000
    URI          /api/v1/ingest/logs
    Format       json
    json_date_key timestamp
    json_date_format iso8601
    Header       Content-Type application/json
    Retry_Limit  5
    tls          Off
```

### parsers.conf

```ini
[PARSER]
    Name         json
    Format       json
    Time_Key     timestamp
    Time_Format  %Y-%m-%dT%H:%M:%S.%LZ
    Time_Keep    On

[PARSER]
    Name         docker
    Format       json
    Time_Key     time
    Time_Format  %Y-%m-%dT%H:%M:%S.%LZ
    Time_Keep    On

[PARSER]
    Name         java_exception
    Format       regex
    Regex        ^(?<timestamp>[^ ]+) (?<level>[^ ]+) (?<logger>[^ ]+) - (?<message>.+)$
```

### extract_exception.lua

```lua
function extract_exception(tag, timestamp, record)
    -- Extract exception from stack trace
    if record["message"] and string.find(record["message"], "Exception") then
        local message = record["message"]
        
        -- Extract exception type
        local exception_type = string.match(message, "([%w%.]+Exception)")
        if exception_type then
            record["exception_type"] = exception_type
        end
        
        -- Extract exception message
        local exception_msg = string.match(message, "Exception: (.+)")
        if exception_msg then
            record["exception_message"] = exception_msg
        end
        
        -- Mark as exception
        record["has_exception"] = true
    end
    
    return 2, timestamp, record
end
```

---

## 🎯 Step 4: Configure Your Service in Luffy

### Via API

```bash
curl -X POST "http://localhost:8000/api/v1/services" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "myapp",
    "name": "My Application",
    "description": "Production web application",
    "repository_url": "https://github.com/your-org/myapp",
    "git_branch": "main",
    "log_processing_enabled": true,
    "rca_generation_enabled": true
  }'
```

### Via UI

1. Open http://localhost:3000
2. Go to "Services" page
3. Click "Add Service"
4. Fill in the form:
   - **Service ID**: `myapp` (must match Fluent Bit config)
   - **Name**: `My Application`
   - **Repository URL**: Your GitHub/GitLab URL
   - **Branch**: `main`
5. Click "Create"

---

## 📊 Step 5: View Your Exceptions

### Dashboard

Open http://localhost:3000 and you'll see:

- **Total Exception Clusters**: Grouped similar exceptions
- **Active Exceptions**: Currently occurring issues
- **RCA Generated**: Exceptions with root cause analysis
- **Exception Trends**: Timeline of exception activity

### API

```bash
# List all exception clusters
curl http://localhost:8000/api/v1/clusters

# Get specific cluster details
curl http://localhost:8000/api/v1/clusters/{cluster_id}

# Get RCA for a cluster
curl http://localhost:8000/api/v1/rca/{cluster_id}
```

---

## 🔍 Complete Example

### Your Application Structure

```
myapp/
├── docker-compose.yml
├── fluent-bit.conf
├── parsers.conf
├── extract_exception.lua
├── logs/
│   └── app.log
└── app/
    └── (your application code)
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  myapp:
    build: .
    ports:
      - "8080:8080"
    volumes:
      - ./logs:/var/log/myapp
    environment:
      - LOG_LEVEL=INFO
      - LOG_FILE=/var/log/myapp/app.log

  fluent-bit:
    image: fluent/fluent-bit:latest
    volumes:
      - ./fluent-bit.conf:/fluent-bit/etc/fluent-bit.conf:ro
      - ./parsers.conf:/fluent-bit/etc/parsers.conf:ro
      - ./extract_exception.lua:/fluent-bit/etc/extract_exception.lua:ro
      - ./logs:/var/log/myapp:ro
    depends_on:
      - myapp
    restart: unless-stopped
```

### fluent-bit.conf

```ini
[SERVICE]
    Flush        5
    Log_Level    info
    Parsers_File parsers.conf

[INPUT]
    Name         tail
    Path         /var/log/myapp/app.log
    Parser       json
    Tag          myapp

[FILTER]
    Name         modify
    Match        *
    Add          service_id myapp
    Add          service_name My Application

[FILTER]
    Name         lua
    Match        *
    script       extract_exception.lua
    call         extract_exception

[FILTER]
    Name         grep
    Match        *
    Regex        level (ERROR|FATAL)

[OUTPUT]
    Name         http
    Match        *
    Host         host.docker.internal
    Port         8000
    URI          /api/v1/ingest/logs
    Format       json
```

### Start Everything

```bash
# Start your application
docker-compose up -d

# Verify logs are being sent
docker-compose logs -f fluent-bit

# Check Luffy received logs
curl http://localhost:8000/api/v1/ingest/metrics
```

---

## 🎛️ Configuration Options

### Service Configuration

```json
{
  "id": "myapp",                          // Unique identifier
  "name": "My Application",               // Display name
  "description": "Production web app",    // Description
  "repository_url": "https://...",        // Git repository
  "git_branch": "main",                   // Branch to index
  "log_processing_enabled": true,         // Enable/disable processing
  "log_fetch_interval_minutes": 30,       // How often to check for logs
  "rca_generation_enabled": true,         // Enable RCA
  "rca_generation_interval_minutes": 15,  // RCA frequency
  "code_indexing_enabled": true           // Enable code context
}
```

### Fluent Bit Filters

**Only send errors:**
```ini
[FILTER]
    Name         grep
    Match        *
    Regex        level (ERROR|FATAL)
```

**Add custom fields:**
```ini
[FILTER]
    Name         modify
    Match        *
    Add          team backend
    Add          region us-west-2
    Add          version 1.2.3
```

**Rate limiting:**
```ini
[FILTER]
    Name         throttle
    Match        *
    Rate         1000
    Window       60
    Interval     1s
```

---

## 🔄 Operations

### Enable/Disable Processing

```bash
# Disable processing (maintenance mode)
curl -X POST "http://localhost:8000/api/v1/services/myapp/toggle-log-processing?enabled=false"

# Re-enable
curl -X POST "http://localhost:8000/api/v1/services/myapp/toggle-log-processing?enabled=true"
```

### Manual Triggers

```bash
# Trigger RCA generation
curl -X POST "http://localhost:8000/api/v1/services/myapp/trigger-rca"

# Trigger code indexing
curl -X POST "http://localhost:8000/api/v1/services/myapp/trigger-code-indexing"

# Trigger log fetch
curl -X POST "http://localhost:8000/api/v1/services/myapp/trigger-log-fetch"
```

### View Logs

```bash
# Application logs
docker-compose logs -f myapp

# Fluent Bit logs
docker-compose logs -f fluent-bit

# Luffy logs
cd ~/luffy-platform
docker-compose logs -f luffy
```

---

## 🐛 Troubleshooting

### Logs Not Appearing in Luffy

**1. Check Fluent Bit is running:**
```bash
docker-compose ps fluent-bit
docker-compose logs fluent-bit
```

**2. Check connectivity:**
```bash
docker-compose exec fluent-bit curl http://host.docker.internal:8000/health
```

**3. Check service exists:**
```bash
curl http://localhost:8000/api/v1/services/myapp
```

**4. Check processing is enabled:**
```bash
curl http://localhost:8000/api/v1/services/myapp/config | jq '.log_processing_enabled'
```

**5. Test manual log ingestion:**
```bash
curl -X POST "http://localhost:8000/api/v1/ingest/logs" \
  -H "Content-Type: application/json" \
  -d '[{
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",
    "level": "ERROR",
    "logger": "com.example.App",
    "message": "Test exception",
    "service_id": "myapp"
  }]'
```

### Fluent Bit Connection Issues

**For Docker Desktop (Mac/Windows):**
```ini
[OUTPUT]
    Host         host.docker.internal
```

**For Linux:**
```ini
[OUTPUT]
    Host         172.17.0.1
```

**For same docker-compose network:**
```ini
[OUTPUT]
    Host         luffy
```

---

## 📈 Best Practices

### 1. Use Service IDs Consistently

Ensure the `service_id` in Fluent Bit matches the service ID in Luffy:

```ini
# fluent-bit.conf
[FILTER]
    Name         modify
    Match        *
    Add          service_id myapp  # ← Must match
```

```bash
# Luffy service
curl -X POST "http://localhost:8000/api/v1/services" \
  -d '{"id": "myapp", ...}'  # ← Must match
```

### 2. Filter Logs Before Sending

Only send ERROR and FATAL logs to reduce noise:

```ini
[FILTER]
    Name         grep
    Match        *
    Regex        level (ERROR|FATAL)
```

### 3. Add Context

Include useful metadata:

```ini
[FILTER]
    Name         modify
    Match        *
    Add          environment production
    Add          hostname ${HOSTNAME}
    Add          version ${APP_VERSION}
```

### 4. Configure Code Repository

Enable RCA with code context:

```bash
curl -X PUT "http://localhost:8000/api/v1/services/myapp" \
  -H "Content-Type: application/json" \
  -d '{
    "repository_url": "https://github.com/your-org/myapp",
    "git_branch": "main",
    "code_indexing_enabled": true
  }'
```

### 5. Monitor Ingestion

```bash
# Check metrics
curl http://localhost:8000/api/v1/ingest/metrics

# Should show:
# - logs_received > 0
# - logs_accepted > 0
# - services_active > 0
```

---

## 🎓 Next Steps

1. ✅ Deploy Luffy Platform
2. ✅ Add Fluent Bit to your application
3. ✅ Configure your service
4. ✅ View exceptions in dashboard
5. 🔜 Set up notifications (Slack, Email)
6. 🔜 Configure code repository for RCA
7. 🔜 Add more services
8. 🔜 Set up alerts

---

## 📚 Additional Resources

- **API Documentation**: http://localhost:8000/docs
- **Fluent Bit Docs**: https://docs.fluentbit.io
- **GitHub Repository**: https://github.com/your-org/luffy

---

## ✅ Quick Reference

```bash
# Deploy Luffy
curl -fsSL https://raw.githubusercontent.com/your-org/luffy/main/deploy.sh | bash

# Create service
curl -X POST http://localhost:8000/api/v1/services -d '{"id":"myapp","name":"My App"}'

# Check health
curl http://localhost:8000/health

# View services
curl http://localhost:8000/api/v1/services

# View clusters
curl http://localhost:8000/api/v1/clusters

# Toggle processing
curl -X POST "http://localhost:8000/api/v1/services/myapp/toggle-log-processing?enabled=false"
```

**That's it! You're ready to track and analyze exceptions! 🎉**
