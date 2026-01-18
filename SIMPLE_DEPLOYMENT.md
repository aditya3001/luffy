# Luffy - Simple One-Command Deployment

## 🎯 Overview

Deploy the entire Luffy Observability Platform with **ONE command**. No complex setup, no manual configuration.

---

## 🚀 Quick Start (3 Steps)

### Step 1: Pull and Run

```bash
# Download and start everything
curl -fsSL https://raw.githubusercontent.com/your-org/luffy/main/deploy.sh | bash
```

**That's it!** The platform will be running at:
- **Frontend**: http://localhost:3000
- **API**: http://localhost:8000
- **Ingest Endpoint**: http://localhost:8000/api/v1/ingest/logs

---

### Step 2: Add Fluent Bit to Your Application

Create `fluent-bit.conf` in your application:

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

[OUTPUT]
    Name         http
    Match        *
    Host         localhost
    Port         8000
    URI          /api/v1/ingest/logs
    Format       json
    Header       Authorization Bearer your-api-token
```

---

### Step 3: View Your Exceptions

Open http://localhost:3000 in your browser and see your exceptions!

---

## 📦 Alternative: Docker Compose (Recommended)

### Option A: Using Pre-built Image

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  luffy:
    image: your-org/luffy:latest
    ports:
      - "3000:3000"  # Frontend
      - "8000:8000"  # API
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - luffy-data:/data
    restart: unless-stopped

volumes:
  luffy-data:
```

**Run:**
```bash
# Set your OpenAI key
export OPENAI_API_KEY=sk-your-key-here

# Start
docker-compose up -d

# View logs
docker-compose logs -f
```

---

### Option B: Build from Source

```bash
# Clone repository
git clone https://github.com/your-org/luffy.git
cd luffy

# Start everything
docker-compose up -d

# Check status
docker-compose ps
```

---

## 🔧 Configuration

### Minimal Configuration (Optional)

Create `.env` file:

```bash
# Required for RCA generation
OPENAI_API_KEY=sk-your-openai-key-here

# Optional: Change default ports
FRONTEND_PORT=3000
API_PORT=8000

# Optional: Database credentials
POSTGRES_PASSWORD=your-secure-password
```

**That's all you need!**

---

## 📝 Adding Your Application

### Step 1: Create Service

```bash
curl -X POST "http://localhost:8000/api/v1/services" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "my-app",
    "name": "My Application",
    "log_processing_enabled": true
  }'
```

### Step 2: Configure Fluent Bit in Your App

**Docker Compose Example:**

```yaml
version: '3.8'

services:
  myapp:
    image: myapp:latest
    # Your app configuration
    
  fluent-bit:
    image: fluent/fluent-bit:latest
    volumes:
      - ./fluent-bit.conf:/fluent-bit/etc/fluent-bit.conf
      - /var/log/myapp:/var/log/myapp:ro
    depends_on:
      - myapp
```

**fluent-bit.conf:**

```ini
[SERVICE]
    Flush        5
    Log_Level    info

[INPUT]
    Name         tail
    Path         /var/log/myapp/*.log
    Parser       json
    Tag          myapp

[FILTER]
    Name         modify
    Match        *
    Add          service_id my-app
    Add          service_name My Application

[OUTPUT]
    Name         http
    Match        *
    Host         host.docker.internal  # For Docker Desktop
    Port         8000
    URI          /api/v1/ingest/logs
    Format       json
    json_date_key timestamp
    json_date_format iso8601
```

### Step 3: Done!

Your exceptions will automatically appear in the dashboard.

---

## 🎯 Complete Example

### Your Application Setup

**1. Application docker-compose.yml:**

```yaml
version: '3.8'

services:
  # Luffy Platform (All-in-One)
  luffy:
    image: your-org/luffy:latest
    ports:
      - "3000:3000"
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=sk-your-key-here
    volumes:
      - luffy-data:/data
    restart: unless-stopped

  # Your Application
  myapp:
    image: myapp:latest
    ports:
      - "8080:8080"
    volumes:
      - ./logs:/var/log/myapp

  # Fluent Bit (Log Shipper)
  fluent-bit:
    image: fluent/fluent-bit:latest
    volumes:
      - ./fluent-bit.conf:/fluent-bit/etc/fluent-bit.conf
      - ./logs:/var/log/myapp:ro
    depends_on:
      - luffy
      - myapp

volumes:
  luffy-data:
```

**2. fluent-bit.conf:**

```ini
[SERVICE]
    Flush        5
    Log_Level    info

[INPUT]
    Name         tail
    Path         /var/log/myapp/*.log
    Parser       json
    Tag          myapp

[FILTER]
    Name         modify
    Match        *
    Add          service_id my-app

[OUTPUT]
    Name         http
    Match        *
    Host         luffy
    Port         8000
    URI          /api/v1/ingest/logs
    Format       json
```

**3. Start Everything:**

```bash
docker-compose up -d
```

**4. View Dashboard:**

Open http://localhost:3000

---

## 🔍 Verification

### Check if Luffy is Running

```bash
# Health check
curl http://localhost:8000/health

# Should return: {"status":"healthy"}
```

### Check if Logs are Being Received

```bash
# View ingestion metrics
curl http://localhost:8000/api/v1/ingest/metrics

# Should show logs_received > 0
```

### Check Dashboard

Open http://localhost:3000 and you should see:
- ✅ Services list
- ✅ Exception clusters
- ✅ Statistics

---

## 🛠️ Management Commands

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f luffy
```

### Restart

```bash
docker-compose restart
```

### Stop

```bash
docker-compose down
```

### Update to Latest Version

```bash
docker-compose pull
docker-compose up -d
```

### Backup Data

```bash
# Backup database
docker-compose exec luffy pg_dump -U luffy_user observability > backup.sql

# Restore
cat backup.sql | docker-compose exec -T luffy psql -U luffy_user observability
```

---

## 📊 Monitoring

### Check Service Status

```bash
curl http://localhost:8000/api/v1/services
```

### Check Exception Clusters

```bash
curl http://localhost:8000/api/v1/clusters
```

### Trigger Manual RCA

```bash
curl -X POST "http://localhost:8000/api/v1/services/my-app/trigger-rca"
```

---

## 🐛 Troubleshooting

### Luffy Not Starting

```bash
# Check logs
docker-compose logs luffy

# Check if ports are available
lsof -i :3000
lsof -i :8000
```

### Logs Not Appearing

**1. Check Fluent Bit is running:**
```bash
docker-compose ps fluent-bit
docker-compose logs fluent-bit
```

**2. Check connectivity:**
```bash
docker-compose exec fluent-bit curl http://luffy:8000/health
```

**3. Check service exists:**
```bash
curl http://localhost:8000/api/v1/services
```

**4. Enable log processing:**
```bash
curl -X POST "http://localhost:8000/api/v1/services/my-app/toggle-log-processing?enabled=true"
```

### Dashboard Not Loading

```bash
# Check if API is responding
curl http://localhost:8000/health

# Check frontend logs
docker-compose logs luffy | grep frontend
```

---

## 🔐 Security

### Production Deployment

**1. Use environment variables for secrets:**

```yaml
services:
  luffy:
    image: your-org/luffy:latest
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - API_TOKEN=${API_TOKEN}
    env_file:
      - .env.production
```

**2. Use HTTPS:**

```yaml
services:
  nginx:
    image: nginx:alpine
    ports:
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - luffy
```

**3. Restrict network access:**

```yaml
services:
  luffy:
    networks:
      - internal
    # Don't expose ports directly, use nginx proxy
```

---

## 📈 Scaling

### Horizontal Scaling

```yaml
services:
  luffy-worker:
    image: your-org/luffy:latest
    command: celery -A src.services.tasks worker
    deploy:
      replicas: 3  # Scale workers
    environment:
      - REDIS_URL=redis://redis:6379
```

### Load Balancing

```yaml
services:
  nginx:
    image: nginx:alpine
    volumes:
      - ./nginx-lb.conf:/etc/nginx/nginx.conf
    ports:
      - "80:80"
    depends_on:
      - luffy-api-1
      - luffy-api-2
      - luffy-api-3
```

---

## 🎓 Next Steps

1. **Configure your first service** via API or UI
2. **Add Fluent Bit** to your applications
3. **Set up code repository** for RCA context
4. **Configure notifications** (Slack, Email)
5. **Monitor your exceptions** in real-time

---

## 📚 Documentation

- **API Reference**: http://localhost:8000/docs
- **Full Installation Guide**: See `INSTALLATION_GUIDE.md`
- **Fluent Bit Integration**: See `docs/FLUENT_BIT_INTEGRATION.md`
- **Architecture**: See `docs/ARCHITECTURE_AND_DEPLOYMENT.md`

---

## 💡 Tips

### Quick Test

```bash
# Send a test exception
curl -X POST "http://localhost:8000/api/v1/ingest/logs" \
  -H "Content-Type: application/json" \
  -d '[{
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",
    "level": "ERROR",
    "logger": "com.example.App",
    "message": "Test exception",
    "exception_type": "NullPointerException",
    "exception_message": "Object reference not set",
    "stack_trace": "at com.example.App.main(App.java:10)",
    "service_id": "my-app"
  }]'
```

### Auto-start on Boot

```bash
# Add to docker-compose.yml
services:
  luffy:
    restart: always
```

### Resource Limits

```yaml
services:
  luffy:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

---

## ✅ Summary

**What You Get:**
- ✅ Complete observability platform
- ✅ Exception clustering and RCA
- ✅ Real-time monitoring dashboard
- ✅ Automatic log processing
- ✅ Code context integration
- ✅ No complex setup

**What You Need:**
- ✅ Docker installed
- ✅ OpenAI API key (for RCA)
- ✅ 5 minutes

**Deployment:**
```bash
docker-compose up -d
```

**That's it! 🎉**
