# Luffy API - Postman Collection

Complete Postman collection for testing all Luffy platform APIs.

## 📦 Files

- `Luffy_API_Collection.json` - Main API collection with all endpoints
- `Luffy_Local_Environment.json` - Local development environment
- `Luffy_Production_Environment.json` - Production environment

## 🚀 Quick Start

### 1. Import Collection

1. Open Postman
2. Click **Import**
3. Select `Luffy_API_Collection.json`
4. Collection will appear in your workspace

### 2. Import Environment

1. Click **Import**
2. Select `Luffy_Local_Environment.json`
3. Select environment from dropdown (top right)

### 3. Start Testing

Run requests in this order:
1. Health Check
2. List Tasks
3. List Clusters

## 📋 API Endpoints

### Health & Info
- `GET /` - Root endpoint
- `GET /health` - Health check
- `GET /api/v1/stats` - System statistics

### Exception Clusters
- `GET /api/v1/clusters` - List clusters
- `GET /api/v1/clusters/{id}` - Get cluster details

### RCA
- `GET /api/v1/rca/{cluster_id}` - Get RCA
- `POST /api/v1/rca/generate` - Generate RCA
- `POST /api/v1/feedback` - Submit feedback

### Task Management
- `GET /api/v1/tasks` - List tasks
- `POST /api/v1/tasks/{name}/enable` - Enable task
- `POST /api/v1/tasks/{name}/disable` - Disable task
- `PUT /api/v1/tasks/{name}` - Update task

### Log Sources
- `GET /api/v1/log-sources` - List sources
- `POST /api/v1/log-sources` - Create source
- `PUT /api/v1/log-sources/{id}` - Update source
- `DELETE /api/v1/log-sources/{id}` - Delete source

## 🧪 Test Scenarios

The collection includes 3 complete test scenarios:

1. **Task Toggle Flow** - Enable/disable tasks
2. **RCA Generation Flow** - Generate and view RCA
3. **Multi-Source Configuration** - Configure log sources

## 🔧 Variables

- `base_url` - API base URL (default: http://localhost:8000)
- `api_version` - API version (default: v1)
- `cluster_id` - Auto-populated from responses
- `task_name` - Task name for testing
- `log_source_id` - Auto-populated from responses

## 📝 Usage Tips

1. Run "List Clusters" first to populate `cluster_id`
2. Run "List Log Sources" to populate `log_source_id`
3. Use test scenarios for complete workflows
4. Check Tests tab for automatic validations

## 🐛 Troubleshooting

**Issue: Connection refused**
- Ensure backend is running: `docker-compose up -d`
- Check URL in environment variables

**Issue: 404 errors**
- Verify API version in environment
- Check endpoint paths in collection

**Issue: Variables not set**
- Run prerequisite requests first
- Check Tests tab for variable setting scripts
