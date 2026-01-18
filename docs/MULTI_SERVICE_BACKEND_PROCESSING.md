# Multi-Service Backend Processing Architecture

## Overview

This document explains how Luffy handles multi-service backend processing with individual service configurations for log processing, RCA generation, code indexing, and notifications.

## 🎯 **Problem Solved**

**Before:** Single global configuration for all services
- ❌ All services used same log fetch interval
- ❌ Single Git repository for all services  
- ❌ Global RCA generation settings
- ❌ No service-specific customization

**After:** Per-service configuration and processing
- ✅ Individual log fetch intervals per service
- ✅ Separate Git repositories per service
- ✅ Service-specific RCA generation settings
- ✅ Custom notification settings per service
- ✅ Independent processing schedules

## 🏗️ **Architecture Components**

### 1. Enhanced Service Model

```python
class Service(Base):
    # Basic Info
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    
    # Git Configuration (per service)
    repository_url = Column(String)
    git_branch = Column(String, default='main')
    git_repo_path = Column(String)
    
    # Processing Configuration
    log_fetch_interval_minutes = Column(Integer, default=30)
    rca_generation_enabled = Column(Boolean, default=True)
    rca_generation_interval_minutes = Column(Integer, default=15)
    code_indexing_enabled = Column(Boolean, default=True)
    code_indexing_interval_hours = Column(Integer, default=24)
    
    # Notification Configuration
    notification_enabled = Column(Boolean, default=True)
    notification_webhook_url = Column(String)
    notification_email = Column(String)
    
    # Status Tracking
    last_log_fetch = Column(DateTime)
    last_rca_generation = Column(DateTime)
    last_code_indexing = Column(DateTime)
```

### 2. Service-Aware Scheduler

The `ServiceScheduler` class manages per-service task scheduling:

```python
class ServiceScheduler:
    def schedule_service_tasks(self):
        """Schedule tasks for all services based on individual configs"""
        
    def _should_fetch_logs(self, service):
        """Check if log fetching is due for this service"""
        
    def _should_generate_rca(self, service):
        """Check if RCA generation is due for this service"""
        
    def _should_index_code(self, service):
        """Check if code indexing is due for this service"""
```

### 3. Enhanced Tasks

All tasks now support service-specific processing:

```python
# Log processing with service filter
fetch_and_process_logs(service_id=None, log_source_id=None)

# RCA generation with service filter  
generate_rca_for_clusters(service_id=None)

# Code indexing with service-specific repo
index_code_repository(service_id=None, repository_path=None, branch='main')
```

## 🔄 **Processing Flow**

### Master Scheduler (Every 5 minutes)
```
schedule_service_tasks() 
├── Get all active services
├── For each service:
│   ├── Check if log fetch is due → Schedule fetch_and_process_logs(service_id)
│   ├── Check if RCA is due → Schedule generate_rca_for_clusters(service_id)  
│   └── Check if code indexing is due → Schedule index_code_repository(service_id, repo_path, branch)
└── Update service status timestamps
```

### Service-Specific Log Processing
```
fetch_and_process_logs(service_id="web-app")
├── Query log_sources WHERE service_id = "web-app"
├── For each log source:
│   ├── Connect using source-specific config (host, port, credentials)
│   ├── Fetch logs using source-specific index_pattern and filters
│   └── Process logs with service context
└── Update service.last_log_fetch
```

### Service-Specific RCA Generation
```
generate_rca_for_clusters(service_id="api-service")
├── Query clusters WHERE service_id = "api-service"
├── Generate RCA for qualifying clusters
├── Use service-specific notification settings
└── Update service.last_rca_generation
```

### Service-Specific Code Indexing
```
index_code_repository(service_id="mobile-app", repo_path="/repos/mobile", branch="develop")
├── Clone/update repository at service-specific path
├── Checkout service-specific branch
├── Index code with service context
└── Update service.last_code_indexing
```

## 📊 **Configuration Examples**

### Service 1: Web Application
```json
{
  "name": "web-app",
  "repository_url": "https://github.com/company/web-app.git",
  "git_branch": "main",
  "git_repo_path": "/repos/web-app",
  "log_fetch_interval_minutes": 15,
  "rca_generation_interval_minutes": 10,
  "code_indexing_interval_hours": 12,
  "notification_webhook_url": "https://slack.com/hooks/web-team"
}
```

### Service 2: API Service  
```json
{
  "name": "api-service",
  "repository_url": "https://github.com/company/api.git", 
  "git_branch": "production",
  "git_repo_path": "/repos/api",
  "log_fetch_interval_minutes": 30,
  "rca_generation_interval_minutes": 20,
  "code_indexing_interval_hours": 24,
  "notification_email": "api-team@company.com"
}
```

### Service 3: Mobile App
```json
{
  "name": "mobile-app",
  "repository_url": "https://github.com/company/mobile.git",
  "git_branch": "develop", 
  "git_repo_path": "/repos/mobile",
  "log_fetch_interval_minutes": 60,
  "rca_generation_enabled": false,
  "code_indexing_interval_hours": 48
}
```

## 🔧 **API Endpoints**

### Service Configuration Management
```bash
# Get service configuration
GET /api/v1/services/{service_id}/config

# Update service configuration  
PUT /api/v1/services/{service_id}/config

# Get service status
GET /api/v1/services/{service_id}/status

# Get all services status
GET /api/v1/services/status
```

### Manual Task Triggering
```bash
# Trigger log fetch for specific service
POST /api/v1/services/{service_id}/trigger-log-fetch

# Trigger RCA generation for specific service
POST /api/v1/services/{service_id}/trigger-rca

# Trigger code indexing for specific service  
POST /api/v1/services/{service_id}/trigger-code-indexing
```

## 🚀 **Setup Instructions**

### 1. Run Migration
```bash
python scripts/migrate_service_config.py
```

### 2. Configure Services
```bash
# Configure web-app service
curl -X PUT "http://localhost:8000/api/v1/services/web-app/config" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "web-app",
    "repository_url": "https://github.com/company/web-app.git",
    "git_branch": "main", 
    "git_repo_path": "/repos/web-app",
    "log_fetch_interval_minutes": 15,
    "rca_generation_interval_minutes": 10
  }'
```

### 3. Monitor Service Status
```bash
# Check all services status
curl "http://localhost:8000/api/v1/services/status"

# Check specific service status
curl "http://localhost:8000/api/v1/services/web-app/status"
```

## 📈 **Benefits**

### 1. **Service Isolation**
- Each service processes independently
- Failures in one service don't affect others
- Custom configurations per service

### 2. **Flexible Scheduling**
- Critical services: 5-minute log fetch intervals
- Less critical services: 60-minute intervals
- Different RCA generation frequencies

### 3. **Multi-Repository Support**
- Each service can have its own Git repository
- Different branches per service (main, develop, production)
- Independent code indexing schedules

### 4. **Custom Notifications**
- Service-specific Slack channels
- Different email lists per service
- Webhook URLs per team

### 5. **Resource Optimization**
- Process only what's needed when it's needed
- Avoid unnecessary processing for inactive services
- Efficient resource utilization

## 🔍 **Monitoring & Debugging**

### Service Status Dashboard
```python
# Get comprehensive service status
{
  "service_id": "web-app",
  "service_name": "Web Application", 
  "is_active": true,
  "last_log_fetch": "2024-01-15T10:30:00Z",
  "last_rca_generation": "2024-01-15T10:25:00Z",
  "last_code_indexing": "2024-01-15T02:00:00Z",
  "log_sources_count": 3,
  "active_log_sources": 2,
  "configuration": {
    "log_fetch_interval_minutes": 15,
    "rca_generation_interval_minutes": 10,
    "code_indexing_interval_hours": 12
  }
}
```

### Task Logs
```bash
# Check service scheduler logs
grep "service-aware task scheduling" /var/log/celery.log

# Check service-specific task logs  
grep "service web-app" /var/log/celery.log
```

## 🎯 **Use Cases**

### 1. **Different Criticality Levels**
- **Critical Services**: 5-minute intervals, immediate RCA
- **Standard Services**: 30-minute intervals, 15-minute RCA  
- **Development Services**: 60-minute intervals, RCA disabled

### 2. **Multi-Team Organizations**
- **Frontend Team**: React app with Slack notifications
- **Backend Team**: API service with email notifications
- **Mobile Team**: React Native app with custom webhook

### 3. **Multi-Environment Support**
- **Production Services**: Main branch, 15-minute intervals
- **Staging Services**: Develop branch, 30-minute intervals
- **Development Services**: Feature branches, 60-minute intervals

## 🔮 **Future Enhancements**

1. **Dynamic Scaling**: Adjust intervals based on exception frequency
2. **Smart Scheduling**: ML-based optimal scheduling times
3. **Cross-Service Correlation**: Detect issues affecting multiple services
4. **Service Dependencies**: Process dependent services in order
5. **Resource Limits**: Per-service resource allocation and limits

---

**Result: Complete multi-service backend processing with individual service configurations, flexible scheduling, and independent processing pipelines.**
