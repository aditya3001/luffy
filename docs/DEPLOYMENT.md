# Deployment Guide

This guide covers deploying the AI-Powered Log Observability Platform to various environments.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Local Development Setup](#local-development-setup)
3. [Docker Deployment](#docker-deployment)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [Cloud Provider Specific Guides](#cloud-provider-specific-guides)
6. [Configuration Management](#configuration-management)
7. [Monitoring & Observability](#monitoring--observability)
8. [Backup & Disaster Recovery](#backup--disaster-recovery)
9. [Security Hardening](#security-hardening)
10. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements

**Minimum:**
- CPU: 4 cores
- RAM: 16 GB
- Storage: 100 GB SSD
- Network: 1 Gbps

**Recommended (Production):**
- CPU: 8-16 cores
- RAM: 32-64 GB
- Storage: 500 GB SSD (with auto-scaling)
- Network: 10 Gbps

### Software Dependencies

- Python 3.9+
- Node.js 18+
- PostgreSQL 14+
- ClickHouse 23+ or OpenSearch 2+
- Redis 7+
- Qdrant 1.7+ or alternative vector DB
- Docker 24+ (for containerized deployment)
- Kubernetes 1.27+ (for K8s deployment)

### External Services

- Log sources (Elasticsearch, CloudWatch, etc.)
- LLM API access (OpenAI, Anthropic, or self-hosted)
- Git repository access
- Object storage (S3, GCS, Azure Blob)

---

## Local Development Setup

### 1. Clone Repository

```bash
git clone https://github.com/yourcompany/luffy.git
cd luffy
```

### 2. Backend Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Copy environment template
cp .env.example .env
# Edit .env with your local settings
```

### 3. Database Setup

```bash
# Start PostgreSQL
docker run -d \
  --name observability-postgres \
  -e POSTGRES_DB=observability \
  -e POSTGRES_USER=admin \
  -e POSTGRES_PASSWORD=yourpassword \
  -p 5432:5432 \
  postgres:14

# Run migrations
python -m alembic upgrade head
```

### 4. ClickHouse Setup

```bash
# Start ClickHouse
docker run -d \
  --name observability-clickhouse \
  -p 8123:8123 \
  -p 9000:9000 \
  clickhouse/clickhouse-server:latest

# Create tables
python scripts/setup_clickhouse.py
```

### 5. Vector Database Setup

```bash
# Start Qdrant
docker run -d \
  --name observability-qdrant \
  -p 6333:6333 \
  -p 6334:6334 \
  qdrant/qdrant:latest
```

### 6. Redis Setup

```bash
# Start Redis
docker run -d \
  --name observability-redis \
  -p 6379:6379 \
  redis:7-alpine
```

### 7. Start Services

```bash
# Start API server
python -m uvicorn services.api.main:app --reload --port 8000

# Start Celery workers (in separate terminals)
celery -A services.workers worker --loglevel=info --queues=ingestion
celery -A services.workers worker --loglevel=info --queues=processing
celery -A services.workers worker --loglevel=info --queues=llm_analysis

# Start Celery beat (scheduler)
celery -A services.workers beat --loglevel=info
```

### 8. Dashboard Setup

```bash
cd dashboard
npm install
npm start
# Dashboard will be available at http://localhost:3000
```

---

## Docker Deployment

### Using Docker Compose

#### 1. Create docker-compose.yml

```yaml
version: '3.8'

services:
  # PostgreSQL
  postgres:
    image: postgres:14
    environment:
      POSTGRES_DB: observability
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U admin"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ClickHouse
  clickhouse:
    image: clickhouse/clickhouse-server:latest
    volumes:
      - clickhouse_data:/var/lib/clickhouse
    ports:
      - "8123:8123"
      - "9000:9000"
    ulimits:
      nofile:
        soft: 262144
        hard: 262144

  # Redis
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  # Qdrant
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage

  # API Server
  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    environment:
      DATABASE_URL: postgresql://admin:${POSTGRES_PASSWORD}@postgres:5432/observability
      REDIS_URL: redis://redis:6379
      CLICKHOUSE_URL: http://clickhouse:8123
      QDRANT_URL: http://qdrant:6333
      OPENAI_API_KEY: ${OPENAI_API_KEY}
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis
      - clickhouse
      - qdrant
    command: uvicorn services.api.main:app --host 0.0.0.0 --port 8000

  # Celery Workers - Ingestion
  worker-ingestion:
    build:
      context: .
      dockerfile: Dockerfile.worker
    environment:
      DATABASE_URL: postgresql://admin:${POSTGRES_PASSWORD}@postgres:5432/observability
      REDIS_URL: redis://redis:6379
      CLICKHOUSE_URL: http://clickhouse:8123
      QDRANT_URL: http://qdrant:6333
    depends_on:
      - postgres
      - redis
    command: celery -A services.workers worker --loglevel=info --queues=ingestion --concurrency=4

  # Celery Workers - Processing
  worker-processing:
    build:
      context: .
      dockerfile: Dockerfile.worker
    environment:
      DATABASE_URL: postgresql://admin:${POSTGRES_PASSWORD}@postgres:5432/observability
      REDIS_URL: redis://redis:6379
      CLICKHOUSE_URL: http://clickhouse:8123
      QDRANT_URL: http://qdrant:6333
    depends_on:
      - postgres
      - redis
    command: celery -A services.workers worker --loglevel=info --queues=processing --concurrency=4

  # Celery Workers - LLM Analysis
  worker-llm:
    build:
      context: .
      dockerfile: Dockerfile.worker
    environment:
      DATABASE_URL: postgresql://admin:${POSTGRES_PASSWORD}@postgres:5432/observability
      REDIS_URL: redis://redis:6379
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      QDRANT_URL: http://qdrant:6333
    depends_on:
      - postgres
      - redis
    command: celery -A services.workers worker --loglevel=info --queues=llm_analysis --concurrency=2

  # Celery Beat
  celery-beat:
    build:
      context: .
      dockerfile: Dockerfile.worker
    environment:
      DATABASE_URL: postgresql://admin:${POSTGRES_PASSWORD}@postgres:5432/observability
      REDIS_URL: redis://redis:6379
    depends_on:
      - postgres
      - redis
    command: celery -A services.workers beat --loglevel=info

  # Dashboard
  dashboard:
    build:
      context: ./dashboard
      dockerfile: Dockerfile
    ports:
      - "3000:80"
    environment:
      REACT_APP_API_URL: http://localhost:8000/api/v1
    depends_on:
      - api

volumes:
  postgres_data:
  clickhouse_data:
  redis_data:
  qdrant_data:
```

#### 2. Create Dockerfiles

**Dockerfile.api**
```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "services.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Dockerfile.worker**
```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Default command (can be overridden in docker-compose)
CMD ["celery", "-A", "services.workers", "worker", "--loglevel=info"]
```

**dashboard/Dockerfile**
```dockerfile
# Build stage
FROM node:18 AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine

COPY --from=builder /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

#### 3. Deploy

```bash
# Create .env file with secrets
cat > .env << EOF
POSTGRES_PASSWORD=your_secure_password
OPENAI_API_KEY=your_openai_key
EOF

# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f api
```

---

## Kubernetes Deployment

### Prerequisites

- Kubernetes cluster (v1.27+)
- kubectl configured
- Helm 3.x installed
- Container registry (Docker Hub, ECR, GCR, etc.)

### 1. Build and Push Images

```bash
# Build images
docker build -t yourregistry/observability-api:v1.0.0 -f Dockerfile.api .
docker build -t yourregistry/observability-worker:v1.0.0 -f Dockerfile.worker .
docker build -t yourregistry/observability-dashboard:v1.0.0 -f dashboard/Dockerfile ./dashboard

# Push to registry
docker push yourregistry/observability-api:v1.0.0
docker push yourregistry/observability-worker:v1.0.0
docker push yourregistry/observability-dashboard:v1.0.0
```

### 2. Create Namespace

```bash
kubectl create namespace observability
```

### 3. Create Secrets

```bash
# Database credentials
kubectl create secret generic db-credentials \
  --from-literal=postgres-password=your_secure_password \
  -n observability

# API keys
kubectl create secret generic api-keys \
  --from-literal=openai-api-key=your_openai_key \
  --from-literal=elasticsearch-api-key=your_es_key \
  -n observability
```

### 4. Deploy PostgreSQL

```yaml
# postgres-deployment.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  namespace: observability
spec:
  serviceName: postgres
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:14
        env:
        - name: POSTGRES_DB
          value: observability
        - name: POSTGRES_USER
          value: admin
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: postgres-password
        ports:
        - containerPort: 5432
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
  volumeClaimTemplates:
  - metadata:
      name: postgres-storage
    spec:
      accessModes: [ "ReadWriteOnce" ]
      resources:
        requests:
          storage: 50Gi
---
apiVersion: v1
kind: Service
metadata:
  name: postgres
  namespace: observability
spec:
  selector:
    app: postgres
  ports:
  - port: 5432
    targetPort: 5432
  clusterIP: None
```

### 5. Deploy Redis

```yaml
# redis-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: observability
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
---
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: observability
spec:
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379
```

### 6. Deploy API Server

```yaml
# api-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  namespace: observability
spec:
  replicas: 3
  selector:
    matchLabels:
      app: api
  template:
    metadata:
      labels:
        app: api
    spec:
      containers:
      - name: api
        image: yourregistry/observability-api:v1.0.0
        env:
        - name: DATABASE_URL
          value: postgresql://admin:$(POSTGRES_PASSWORD)@postgres:5432/observability
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: postgres-password
        - name: REDIS_URL
          value: redis://redis:6379
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: api-keys
              key: openai-api-key
        ports:
        - containerPort: 8000
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: api
  namespace: observability
spec:
  selector:
    app: api
  ports:
  - port: 8000
    targetPort: 8000
  type: ClusterIP
```

### 7. Deploy Workers

```yaml
# workers-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: worker-processing
  namespace: observability
spec:
  replicas: 5
  selector:
    matchLabels:
      app: worker-processing
  template:
    metadata:
      labels:
        app: worker-processing
    spec:
      containers:
      - name: worker
        image: yourregistry/observability-worker:v1.0.0
        command: ["celery", "-A", "services.workers", "worker", "--loglevel=info", "--queues=processing", "--concurrency=4"]
        env:
        - name: DATABASE_URL
          value: postgresql://admin:$(POSTGRES_PASSWORD)@postgres:5432/observability
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: postgres-password
        - name: REDIS_URL
          value: redis://redis:6379
        resources:
          requests:
            memory: "1Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: worker-llm
  namespace: observability
spec:
  replicas: 2
  selector:
    matchLabels:
      app: worker-llm
  template:
    metadata:
      labels:
        app: worker-llm
    spec:
      containers:
      - name: worker
        image: yourregistry/observability-worker:v1.0.0
        command: ["celery", "-A", "services.workers", "worker", "--loglevel=info", "--queues=llm_analysis", "--concurrency=2"]
        env:
        - name: DATABASE_URL
          value: postgresql://admin:$(POSTGRES_PASSWORD)@postgres:5432/observability
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: postgres-password
        - name: REDIS_URL
          value: redis://redis:6379
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: api-keys
              key: openai-api-key
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
```

### 8. Deploy Ingress

```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: observability-ingress
  namespace: observability
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - observability.yourcompany.com
    secretName: observability-tls
  rules:
  - host: observability.yourcompany.com
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: api
            port:
              number: 8000
      - path: /
        pathType: Prefix
        backend:
          service:
            name: dashboard
            port:
              number: 80
```

### 9. Deploy All Resources

```bash
kubectl apply -f postgres-deployment.yaml
kubectl apply -f redis-deployment.yaml
kubectl apply -f qdrant-deployment.yaml
kubectl apply -f api-deployment.yaml
kubectl apply -f workers-deployment.yaml
kubectl apply -f dashboard-deployment.yaml
kubectl apply -f ingress.yaml

# Check status
kubectl get pods -n observability
kubectl get services -n observability
kubectl get ingress -n observability
```

### 10. Auto-scaling

```yaml
# hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-hpa
  namespace: observability
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

---

## Cloud Provider Specific Guides

### AWS Deployment

#### Using EKS (Elastic Kubernetes Service)

```bash
# Create EKS cluster
eksctl create cluster \
  --name observability-cluster \
  --region us-east-1 \
  --nodegroup-name standard-workers \
  --node-type t3.xlarge \
  --nodes 3 \
  --nodes-min 1 \
  --nodes-max 10 \
  --managed

# Update kubeconfig
aws eks update-kubeconfig --region us-east-1 --name observability-cluster

# Deploy application (follow K8s steps above)
```

#### Using RDS for PostgreSQL

```bash
# Create RDS instance
aws rds create-db-instance \
  --db-instance-identifier observability-db \
  --db-instance-class db.r5.large \
  --engine postgres \
  --engine-version 14.7 \
  --master-username admin \
  --master-user-password your_password \
  --allocated-storage 100 \
  --storage-type gp3
```

#### Using S3 for Object Storage

Configure in your `.env`:
```
S3_BUCKET=observability-raw-logs
AWS_REGION=us-east-1
```

### GCP Deployment

#### Using GKE (Google Kubernetes Engine)

```bash
# Create GKE cluster
gcloud container clusters create observability-cluster \
  --zone us-central1-a \
  --num-nodes 3 \
  --machine-type n1-standard-4 \
  --enable-autoscaling \
  --min-nodes 1 \
  --max-nodes 10

# Get credentials
gcloud container clusters get-credentials observability-cluster --zone us-central1-a
```

### Azure Deployment

#### Using AKS (Azure Kubernetes Service)

```bash
# Create AKS cluster
az aks create \
  --resource-group observability-rg \
  --name observability-cluster \
  --node-count 3 \
  --node-vm-size Standard_D4s_v3 \
  --enable-cluster-autoscaler \
  --min-count 1 \
  --max-count 10

# Get credentials
az aks get-credentials --resource-group observability-rg --name observability-cluster
```

---

## Configuration Management

### Environment Variables

Key environment variables to configure:

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/observability
CLICKHOUSE_URL=http://clickhouse:8123
REDIS_URL=redis://redis:6379
QDRANT_URL=http://qdrant:6333

# Log Sources
LOG_SOURCE=elasticsearch
ELASTICSEARCH_URL=https://logs.company.com
ELASTICSEARCH_API_KEY=your_key

# LLM
LLM_PROVIDER=openai
OPENAI_API_KEY=your_key

# Storage
S3_BUCKET=observability-logs
AWS_REGION=us-east-1

# Application
API_PORT=8000
DASHBOARD_PORT=3000
LOG_LEVEL=INFO
WORKERS_CONCURRENCY=4
```

### Using ConfigMaps (Kubernetes)

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
  namespace: observability
data:
  LOG_LEVEL: "INFO"
  WORKERS_CONCURRENCY: "4"
  LLM_PROVIDER: "openai"
```

---

## Monitoring & Observability

### Prometheus Metrics

```python
# Add to your FastAPI app
from prometheus_client import Counter, Histogram, generate_latest

rca_generated = Counter('rca_generated_total', 'Total RCA generated')
rca_latency = Histogram('rca_latency_seconds', 'RCA generation latency')

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type="text/plain")
```

### Grafana Dashboards

Import pre-built dashboards from `monitoring/grafana/dashboards/`

### Health Checks

```python
# services/api/main.py
@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.get("/ready")
def readiness_check():
    # Check dependencies
    db_ready = check_database()
    redis_ready = check_redis()
    return {"ready": db_ready and redis_ready}
```

---

## Backup & Disaster Recovery

### Database Backups

```bash
# PostgreSQL backup
pg_dump -h localhost -U admin observability > backup_$(date +%Y%m%d).sql

# Restore
psql -h localhost -U admin observability < backup_20251012.sql
```

### Automated Backups (Kubernetes)

```yaml
# backup-cronjob.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: postgres-backup
  namespace: observability
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: backup
            image: postgres:14
            command:
            - /bin/sh
            - -c
            - pg_dump -h postgres -U admin observability | gzip > /backups/backup_$(date +%Y%m%d).sql.gz
            volumeMounts:
            - name: backups
              mountPath: /backups
          volumes:
          - name: backups
            persistentVolumeClaim:
              claimName: backup-pvc
          restartPolicy: OnFailure
```

---

## Security Hardening

### 1. Network Policies

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-network-policy
  namespace: observability
spec:
  podSelector:
    matchLabels:
      app: api
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: ingress-nginx
    ports:
    - protocol: TCP
      port: 8000
```

### 2. RBAC

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: observability-role
  namespace: observability
rules:
- apiGroups: [""]
  resources: ["pods", "services"]
  verbs: ["get", "list"]
```

### 3. Secret Management

Use external secret managers:
- AWS Secrets Manager
- GCP Secret Manager
- Azure Key Vault
- HashiCorp Vault

---

## Troubleshooting

### Common Issues

**1. Workers not processing jobs**
```bash
# Check Celery workers
celery -A services.workers inspect active

# Check Redis connection
redis-cli ping

# Check logs
kubectl logs -f deployment/worker-processing -n observability
```

**2. High memory usage**
```bash
# Check resource usage
kubectl top pods -n observability

# Scale down if needed
kubectl scale deployment/worker-processing --replicas=2 -n observability
```

**3. Database connection issues**
```bash
# Test connection
psql -h postgres -U admin -d observability

# Check connection pool
# Add to your app: SQLALCHEMY_POOL_SIZE=20
```

### Logging

```bash
# View API logs
kubectl logs -f deployment/api -n observability

# View worker logs
kubectl logs -f deployment/worker-processing -n observability

# View all logs with labels
kubectl logs -l app=api -n observability --tail=100
```

---

## Scaling Recommendations

### Vertical Scaling
- API servers: 2-4 GB RAM per instance
- Processing workers: 2-4 GB RAM per instance
- LLM workers: 1-2 GB RAM per instance

### Horizontal Scaling
- API servers: Scale based on request rate (target: <100ms p99)
- Processing workers: Scale based on queue depth
- LLM workers: Scale carefully due to cost

---

## Support

For deployment support:
- Documentation: `/docs`
- Issues: GitHub Issues
- Email: devops@yourcompany.com
