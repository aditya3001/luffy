# Luffy Observability Platform - Installation Guide

## 🎯 Overview

This guide provides **multiple installation approaches** for deploying the Luffy observability platform, from simple one-command installation to production-ready Kubernetes deployment.

---

## 📋 Table of Contents

1. [Quick Start (Recommended)](#1-quick-start-recommended)
2. [Docker Compose Installation](#2-docker-compose-installation)
3. [Manual Installation](#3-manual-installation)
4. [Kubernetes Deployment](#4-kubernetes-deployment)
5. [Adding Services with Fluent Bit](#5-adding-services-with-fluent-bit)
6. [Post-Installation Configuration](#6-post-installation-configuration)
7. [Troubleshooting](#7-troubleshooting)

---

## 1. Quick Start (Recommended)

### One-Command Installation

```bash
# Clone repository
git clone https://github.com/your-org/luffy.git
cd luffy

# Run installation script
./scripts/install.sh
```

The installation script will:
- ✅ Check prerequisites (Docker, Docker Compose)
- ✅ Set up environment variables
- ✅ Start all required services
- ✅ Initialize database
- ✅ Run migrations
- ✅ Create default service
- ✅ Provide access URLs

### What You Get

After installation:
- 🌐 **Frontend**: http://localhost:3000
- 🔧 **API**: http://localhost:8000
- 📚 **API Docs**: http://localhost:8000/docs
- 🗄️ **PostgreSQL**: localhost:5432
- 🔴 **Redis**: localhost:6379
- 📊 **Qdrant**: http://localhost:6333/dashboard
- 🔍 **OpenSearch**: http://localhost:9200

---

## 2. Docker Compose Installation

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- 8GB RAM minimum
- 20GB disk space

### Step-by-Step Installation

#### Step 1: Clone Repository

```bash
git clone https://github.com/your-org/luffy.git
cd luffy
```

#### Step 2: Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env file with your settings
nano .env
```

**Key Environment Variables:**

```bash
# Database
POSTGRES_USER=luffy_user
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=observability

# Redis
REDIS_URL=redis://redis:6379/0

# OpenSearch (optional)
OPENSEARCH_HOST=opensearch
OPENSEARCH_PORT=9200
OPENSEARCH_USER=admin
OPENSEARCH_PASSWORD=admin

# LLM Configuration
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4

# Git Repository (for code indexing)
GIT_REPO_PATH=/path/to/your/repo
GIT_BRANCH=main
```

#### Step 3: Choose Deployment Mode

**Option A: Simple Mode (Recommended for Testing)**

```bash
make simple-up
```

Services included:
- PostgreSQL (metadata storage)
- Redis (cache & queue)
- Qdrant (vector database)
- FastAPI (API server)
- Celery (async workers)

**Option B: Full Mode (Production)**

```bash
make up
```

Additional services:
- OpenSearch (log storage)
- Fluent Bit (log collection)
- Frontend (React UI)

#### Step 4: Initialize Database

```bash
make init-db
```

This will:
- Create database schema
- Run migrations
- Create default admin user
- Seed initial data

#### Step 5: Verify Installation

```bash
make health
```

Expected output:
```json
{
  "status": "healthy",
  "services": {
    "postgres": "connected",
    "redis": "connected",
    "qdrant": "connected",
    "opensearch": "connected"
  }
}
```

#### Step 6: Access UI

Open browser: http://localhost:3000

---

## 3. Manual Installation

### Prerequisites

- Python 3.10+
- Node.js 18+
- PostgreSQL 15+
- Redis 7+
- Qdrant (optional)
- OpenSearch (optional)

### Backend Setup

#### Step 1: Install Python Dependencies

```bash
cd luffy

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

#### Step 2: Configure Environment

```bash
cp .env.example .env
nano .env
```

Update database URLs to point to your local services:

```bash
DATABASE_URL=postgresql://luffy_user:password@localhost:5432/observability
REDIS_URL=redis://localhost:6379/0
QDRANT_URL=http://localhost:6333
```

#### Step 3: Initialize Database

```bash
# Create database
createdb observability

# Run migrations
python scripts/init_db.py
python scripts/migrate_log_processing_toggle.py
```

#### Step 4: Start Backend Services

```bash
# Terminal 1: API Server
uvicorn src.services.api:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Celery Worker
celery -A src.services.tasks worker --loglevel=info

# Terminal 3: Celery Beat (scheduler)
celery -A src.services.tasks beat --loglevel=info
```

### Frontend Setup

#### Step 1: Install Dependencies

```bash
cd frontend
npm install
```

#### Step 2: Configure API URL

```bash
# Create .env file
echo "VITE_API_URL=http://localhost:8000/api/v1" > .env
```

#### Step 3: Start Frontend

```bash
npm run dev
```

Frontend will be available at: http://localhost:3000

---

## 4. Kubernetes Deployment

### Prerequisites

- Kubernetes cluster (1.24+)
- kubectl configured
- Helm 3.0+
- 16GB RAM minimum
- 50GB storage

### Deployment Steps

#### Step 1: Create Namespace

```bash
kubectl create namespace luffy
```

#### Step 2: Deploy Using Helm

```bash
# Add Helm repository
helm repo add luffy https://charts.luffy.io
helm repo update

# Install Luffy
helm install luffy luffy/luffy \
  --namespace luffy \
  --set postgresql.enabled=true \
  --set redis.enabled=true \
  --set opensearch.enabled=true \
  --set ingress.enabled=true \
  --set ingress.host=luffy.yourdomain.com
```

#### Step 3: Verify Deployment

```bash
kubectl get pods -n luffy
```

Expected output:
```
NAME                              READY   STATUS    RESTARTS   AGE
luffy-api-xxx                     1/1     Running   0          2m
luffy-worker-xxx                  1/1     Running   0          2m
luffy-beat-xxx                    1/1     Running   0          2m
luffy-frontend-xxx                1/1     Running   0          2m
luffy-postgresql-0                1/1     Running   0          2m
luffy-redis-0                     1/1     Running   0          2m
luffy-opensearch-0                1/1     Running   0          2m
```

#### Step 4: Access Services

```bash
# Port forward (for testing)
kubectl port-forward -n luffy svc/luffy-frontend 3000:80
kubectl port-forward -n luffy svc/luffy-api 8000:8000

# Or use Ingress
echo "Access at: https://luffy.yourdomain.com"
```

### Kubernetes Configuration Files

See `k8s/` directory for:
- `deployment.yaml` - Application deployments
- `service.yaml` - Service definitions
- `ingress.yaml` - Ingress configuration
- `configmap.yaml` - Configuration
- `secrets.yaml` - Secrets (template)
- `pvc.yaml` - Persistent volume claims

---

## 5. Adding Services with Fluent Bit

### Overview

After Luffy is installed, you need to configure Fluent Bit to send logs from your services to Luffy's OpenSearch.

### Step-by-Step Guide

#### Step 1: Install Fluent Bit on Your Service

**Docker Compose:**

```yaml
# Add to your service's docker-compose.yml
services:
  your-app:
    image: your-app:latest
    # ... your app configuration

  fluent-bit:
    image: fluent/fluent-bit:2.1
    volumes:
      - ./fluent-bit/fluent-bit.conf:/fluent-bit/etc/fluent-bit.conf
      - ./fluent-bit/parsers.conf:/fluent-bit/etc/parsers.conf
      - ./fluent-bit/scripts:/fluent-bit/scripts
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
    depends_on:
      - your-app
    networks:
      - luffy-network

networks:
  luffy-network:
    external: true
```

**Kubernetes:**

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: fluent-bit-config
  namespace: your-namespace
data:
  fluent-bit.conf: |
    [SERVICE]
        Flush        5
        Daemon       Off
        Log_Level    info

    [INPUT]
        Name              tail
        Path              /var/log/containers/*your-app*.log
        Parser            docker
        Tag               kube.*
        Refresh_Interval  5
        Mem_Buf_Limit     5MB

    [FILTER]
        Name                kubernetes
        Match               kube.*
        Kube_URL            https://kubernetes.default.svc:443
        Kube_CA_File        /var/run/secrets/kubernetes.io/serviceaccount/ca.crt
        Kube_Token_File     /var/run/secrets/kubernetes.io/serviceaccount/token
        Merge_Log           On
        K8S-Logging.Parser  On
        K8S-Logging.Exclude On

    [OUTPUT]
        Name            opensearch
        Match           *
        Host            luffy-opensearch.luffy.svc.cluster.local
        Port            9200
        Index           logs-your-service
        Type            _doc
        HTTP_User       admin
        HTTP_Passwd     admin
        tls             Off
        Suppress_Type_Name On
```

#### Step 2: Configure Fluent Bit

Create `fluent-bit/fluent-bit.conf`:

```ini
[SERVICE]
    Flush        5
    Daemon       Off
    Log_Level    info
    Parsers_File parsers.conf

[INPUT]
    Name              tail
    Path              /var/log/your-app/*.log
    Parser            json
    Tag               your-service
    Refresh_Interval  5
    Mem_Buf_Limit     5MB
    Skip_Long_Lines   On

[FILTER]
    Name    lua
    Match   *
    script  /fluent-bit/scripts/extract_exception.lua
    call    extract_exception

[OUTPUT]
    Name            opensearch
    Match           *
    Host            ${OPENSEARCH_HOST}
    Port            ${OPENSEARCH_PORT}
    Index           logs-your-service-${ENVIRONMENT}
    Type            _doc
    HTTP_User       ${OPENSEARCH_USER}
    HTTP_Passwd     ${OPENSEARCH_PASSWORD}
    tls             ${OPENSEARCH_TLS}
    tls.verify      ${OPENSEARCH_TLS_VERIFY}
    Suppress_Type_Name On
    Retry_Limit     5
```

#### Step 3: Configure Parsers

Create `fluent-bit/parsers.conf`:

```ini
[PARSER]
    Name        json
    Format      json
    Time_Key    timestamp
    Time_Format %Y-%m-%dT%H:%M:%S.%L%z
    Time_Keep   On

[MULTILINE_PARSER]
    name          java_stacktrace
    Type          regex
    Flush_Timeout 5000
    Rule start_state  ^(?<time>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3})\s+\[[^\]]+\]\s+(ERROR|WARN|FATAL)\s+.* cont
    Rule cont         ^(?!\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}).* cont
```

#### Step 4: Add Exception Extraction Script

Copy from Luffy repository:

```bash
cp /path/to/luffy/fluent-bit/scripts/extract_exception.lua \
   ./fluent-bit/scripts/extract_exception.lua
```

#### Step 5: Configure Service in Luffy

**Via UI:**

1. Go to http://localhost:3000/services
2. Click "Add Service"
3. Fill in details:
   - Name: `your-service`
   - Description: `Your service description`
   - Git Repository: `https://github.com/your-org/your-repo`
   - Git Branch: `main`
4. Click "Save"

5. Go to "Log Sources" tab
6. Click "Add Log Source"
7. Fill in details:
   - Name: `your-service-logs`
   - Type: `opensearch`
   - Host: `opensearch` (or `localhost` if external)
   - Port: `9200`
   - Index Pattern: `logs-your-service-*`
   - Username: `admin`
   - Password: `admin`
8. Click "Test Connection"
9. Click "Save"

**Via API:**

```bash
# Create service
curl -X POST "http://localhost:8000/api/v1/services" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "your-service",
    "name": "Your Service",
    "description": "Your service description",
    "repository_url": "https://github.com/your-org/your-repo",
    "git_branch": "main",
    "log_processing_enabled": true
  }'

# Create log source
curl -X POST "http://localhost:8000/api/v1/log-sources" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "your-service-logs",
    "service_id": "your-service",
    "name": "Your Service Logs",
    "source_type": "opensearch",
    "host": "opensearch",
    "port": 9200,
    "username": "admin",
    "password": "admin",
    "index_pattern": "logs-your-service-*",
    "fetch_enabled": true,
    "fetch_interval_minutes": 30
  }'
```

#### Step 6: Start Fluent Bit

```bash
docker-compose up -d fluent-bit
```

#### Step 7: Verify Log Flow

```bash
# Check Fluent Bit logs
docker-compose logs -f fluent-bit

# Check OpenSearch indices
curl "http://localhost:9200/_cat/indices/logs-your-service-*?v"

# Check Luffy dashboard
# Go to http://localhost:3000/dashboard
# Select your service
# You should see exceptions appearing
```

---

## 6. Post-Installation Configuration

### Create Admin User

```bash
python scripts/create_admin_user.py \
  --email admin@example.com \
  --password your_secure_password
```

### Configure LLM

```bash
# Edit .env
OPENAI_API_KEY=sk-your-api-key
OPENAI_MODEL=gpt-4
```

### Configure Git Access

For private repositories:

```bash
# Edit .env
GIT_ACCESS_TOKEN=ghp_your_github_token
```

Or configure per service via UI.

### Enable Code Indexing

```bash
# Trigger code indexing for a service
curl -X POST "http://localhost:8000/api/v1/services/your-service/trigger-code-indexing"
```

### Configure Notifications

**Slack:**

```bash
# Via UI: Services → Your Service → Configuration
# Set Notification Webhook URL: https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

**Email:**

```bash
# Edit .env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

---

## 7. Troubleshooting

### Common Issues

#### Issue: Services not starting

**Solution:**

```bash
# Check logs
make logs

# Check service status
make ps

# Restart services
make restart
```

#### Issue: Database connection failed

**Solution:**

```bash
# Check PostgreSQL
docker-compose exec postgres pg_isready -U luffy_user

# Check connection string in .env
DATABASE_URL=postgresql://luffy_user:password@postgres:5432/observability
```

#### Issue: Logs not appearing in Luffy

**Solution:**

```bash
# Check Fluent Bit logs
docker-compose logs fluent-bit

# Check OpenSearch
curl "http://localhost:9200/_cat/indices?v"

# Check log source configuration
curl "http://localhost:8000/api/v1/log-sources"

# Test log source connection
curl -X POST "http://localhost:8000/api/v1/log-sources/your-source-id/test"
```

#### Issue: RCA not generating

**Solution:**

```bash
# Check LLM configuration
curl "http://localhost:8000/api/v1/health"

# Trigger RCA manually
curl -X POST "http://localhost:8000/api/v1/services/your-service/trigger-rca"

# Check Celery worker logs
make logs-worker
```

#### Issue: Frontend not loading

**Solution:**

```bash
# Check API URL in frontend/.env
VITE_API_URL=http://localhost:8000/api/v1

# Rebuild frontend
cd frontend
npm run build

# Check API health
curl "http://localhost:8000/health"
```

### Health Checks

```bash
# Overall health
make health

# Individual service health
curl "http://localhost:8000/health"
curl "http://localhost:6333/healthz"
curl "http://localhost:9200/_cluster/health"
```

### Logs

```bash
# All logs
make logs

# Specific service logs
make logs-api
make logs-worker
make logs-frontend

# Follow logs
docker-compose logs -f api
```

### Reset Installation

```bash
# Stop and remove everything
make clean-all

# Start fresh
make up
make init-db
```

---

## 📚 Additional Resources

- **Documentation**: `/docs` directory
- **API Reference**: http://localhost:8000/docs
- **Postman Collection**: `/postman` directory
- **Example Configurations**: `/config` directory
- **Migration Scripts**: `/scripts` directory

---

## 🆘 Support

For issues and questions:
1. Check documentation in `/docs`
2. Review troubleshooting section
3. Check GitHub issues
4. Contact support team

---

## 📝 Next Steps

After installation:

1. ✅ Create services via UI
2. ✅ Configure log sources
3. ✅ Add Fluent Bit to your applications
4. ✅ Configure Git repositories for code indexing
5. ✅ Set up notifications (Slack/Email)
6. ✅ Enable log processing toggle
7. ✅ Monitor dashboard for exceptions
8. ✅ Generate RCA for clusters
9. ✅ Review and provide feedback

**Happy Observing! 🚀**
