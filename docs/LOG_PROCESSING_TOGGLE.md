# Log Processing Toggle - UI-Controlled Processing Flow

## Overview

This document describes the implementation of the **log processing toggle** feature, which allows users to enable/disable log processing per service through the UI.

## Changes Summary

### 🎯 What Changed:

**1. Removed Scheduled Tasks:**
- ❌ Removed RCA generation scheduling (was every 15 minutes)
- ❌ Removed code indexing scheduling (was daily at 2 AM)
- ✅ Kept log fetching schedule (respects toggle)
- ✅ Kept cleanup task (weekly)

**2. Added Log Processing Toggle:**
- ✅ Master toggle per service: `log_processing_enabled`
- ✅ When disabled, log processing is skipped for that service
- ✅ RCA and code indexing can still be triggered manually
- ✅ UI control through API endpoint

**3. On-Demand Only:**
- RCA generation: Manual trigger only (no scheduling)
- Code indexing: Manual trigger only (no scheduling)
- Log processing: Scheduled but respects toggle

## Architecture

### Database Model

**Service Table - New Field:**
```sql
ALTER TABLE services 
ADD COLUMN log_processing_enabled BOOLEAN DEFAULT TRUE;
```

### Backend Flow

```
Periodic Task (every N minutes)
├── fetch_and_process_logs()
├── For each log source:
│   ├── Get service
│   ├── Check: service.log_processing_enabled?
│   │   ├── TRUE → Process logs
│   │   └── FALSE → Skip (log and continue)
│   └── Continue to next source
```

### API Endpoints

**Toggle Endpoint:**
```
POST /api/v1/services/{service_id}/toggle-log-processing?enabled={true|false}
```

**Response:**
```json
{
  "message": "Log processing enabled for service Web Application",
  "service_id": "web-app",
  "service_name": "Web Application",
  "log_processing_enabled": true
}
```

**Manual Trigger Endpoints (Still Available):**
- `POST /api/v1/services/{service_id}/trigger-log-fetch` - Manual log fetch
- `POST /api/v1/services/{service_id}/trigger-rca` - Manual RCA generation
- `POST /api/v1/services/{service_id}/trigger-code-indexing` - Manual code indexing

## Usage

### 1. Run Migration

```bash
python scripts/migrate_log_processing_toggle.py
```

This will:
- Add `log_processing_enabled` column to services table
- Set all existing services to `enabled` (backward compatible)

### 2. Restart Services

```bash
# Restart backend
uvicorn src.services.api:app --reload

# Restart Celery worker
celery -A src.services.tasks worker --loglevel=info

# Restart Celery beat
celery -A src.services.tasks beat --loglevel=info
```

### 3. Use UI to Toggle

**Frontend Integration (To Be Implemented):**

```typescript
import { servicesAPI } from '@/api/client';

// Enable log processing
await servicesAPI.toggleLogProcessing(serviceId, true);

// Disable log processing
await servicesAPI.toggleLogProcessing(serviceId, false);
```

**Example UI Component:**

```typescript
const LogProcessingToggle = ({ service }: { service: Service }) => {
  const [enabled, setEnabled] = useState(service.log_processing_enabled);
  
  const toggleMutation = useMutation({
    mutationFn: (enabled: boolean) => 
      servicesAPI.toggleLogProcessing(service.id, enabled),
    onSuccess: (data) => {
      setEnabled(data.log_processing_enabled);
      message.success(data.message);
    },
  });
  
  return (
    <Switch
      checked={enabled}
      onChange={(checked) => toggleMutation.mutate(checked)}
      checkedChildren="Processing"
      unCheckedChildren="Paused"
    />
  );
};
```

## Behavior

### When Log Processing is ENABLED (Default):

- ✅ Periodic log fetch runs normally
- ✅ Logs are fetched from OpenSearch/Elasticsearch
- ✅ Exceptions are extracted and clustered
- ✅ Notifications are sent
- ✅ RCA can be triggered manually
- ✅ Code indexing can be triggered manually

### When Log Processing is DISABLED:

- ❌ Periodic log fetch skips this service
- ❌ No logs are fetched
- ❌ No exceptions are extracted
- ❌ No clustering happens
- ✅ RCA can still be triggered manually for existing clusters
- ✅ Code indexing can still be triggered manually
- ✅ Existing data remains accessible

## Use Cases

### 1. Maintenance Window

Disable log processing during maintenance to avoid false alerts:

```bash
curl -X POST "http://localhost:8000/api/v1/services/web-app/toggle-log-processing?enabled=false"
```

### 2. Development/Testing

Disable processing for dev services to save resources:

```bash
curl -X POST "http://localhost:8000/api/v1/services/dev-api/toggle-log-processing?enabled=false"
```

### 3. Temporary Pause

Pause processing while investigating an issue:

```bash
# Disable
curl -X POST "http://localhost:8000/api/v1/services/web-app/toggle-log-processing?enabled=false"

# Re-enable when ready
curl -X POST "http://localhost:8000/api/v1/services/web-app/toggle-log-processing?enabled=true"
```

### 4. Cost Optimization

Disable processing for low-priority services:

```bash
curl -X POST "http://localhost:8000/api/v1/services/legacy-app/toggle-log-processing?enabled=false"
```

## Monitoring

### Check Service Status

```bash
curl "http://localhost:8000/api/v1/services/web-app/status"
```

**Response includes:**
```json
{
  "service_id": "web-app",
  "service_name": "Web Application",
  "log_processing_enabled": true,
  "last_log_fetch": "2024-12-24T17:30:00Z",
  "log_sources_count": 3,
  "active_log_sources": 2
}
```

### Check Logs

**When processing is disabled:**
```
[INFO] [Task abc123] Log processing disabled for service Web Application, skipping
```

**When processing is enabled:**
```
[INFO] [Task abc123] Fetching from log source: Production OpenSearch (opensearch)
[INFO] [Task abc123] Fetched 150 logs from Production OpenSearch
```

## Migration Guide

### For Existing Deployments:

1. **Backup Database:**
   ```bash
   pg_dump luffy > backup_before_toggle.sql
   ```

2. **Run Migration:**
   ```bash
   python scripts/migrate_log_processing_toggle.py
   ```

3. **Verify:**
   ```bash
   psql luffy -c "SELECT id, name, log_processing_enabled FROM services;"
   ```

4. **Restart Services:**
   ```bash
   # Stop all services
   pkill -f "celery"
   pkill -f "uvicorn"
   
   # Start backend
   uvicorn src.services.api:app --reload &
   
   # Start Celery worker
   celery -A src.services.tasks worker --loglevel=info &
   
   # Start Celery beat
   celery -A src.services.tasks beat --loglevel=info &
   ```

### For New Deployments:

The `log_processing_enabled` field is included in the Service model with default value `TRUE`, so no migration is needed.

## API Reference

### Toggle Log Processing

**Endpoint:**
```
POST /api/v1/services/{service_id}/toggle-log-processing
```

**Query Parameters:**
- `enabled` (required): `true` or `false`

**Response:**
```json
{
  "message": "Log processing enabled for service Web Application",
  "service_id": "web-app",
  "service_name": "Web Application",
  "log_processing_enabled": true
}
```

**Status Codes:**
- `200 OK`: Toggle successful
- `404 Not Found`: Service not found
- `500 Internal Server Error`: Database error

### Get Service Configuration

**Endpoint:**
```
GET /api/v1/services/{service_id}/config
```

**Response includes:**
```json
{
  "id": "web-app",
  "name": "Web Application",
  "log_processing_enabled": true,
  "log_fetch_interval_minutes": 30,
  ...
}
```

### Update Service Configuration

**Endpoint:**
```
PUT /api/v1/services/{service_id}/config
```

**Request Body:**
```json
{
  "log_processing_enabled": false,
  "log_fetch_interval_minutes": 60,
  ...
}
```

## Troubleshooting

### Issue: Logs Not Being Processed

**Check:**
1. Is log processing enabled?
   ```bash
   curl "http://localhost:8000/api/v1/services/web-app/config" | jq '.log_processing_enabled'
   ```

2. Are log sources active?
   ```bash
   curl "http://localhost:8000/api/v1/services/web-app/status" | jq '.active_log_sources'
   ```

3. Check Celery logs:
   ```bash
   tail -f celery_worker.log | grep "Log processing"
   ```

### Issue: Toggle Not Working

**Check:**
1. Database connection:
   ```bash
   psql luffy -c "SELECT 1;"
   ```

2. Service exists:
   ```bash
   psql luffy -c "SELECT id, name FROM services WHERE id='web-app';"
   ```

3. API logs:
   ```bash
   tail -f api.log | grep "toggle-log-processing"
   ```

### Issue: Migration Failed

**Rollback:**
```bash
# Restore from backup
psql luffy < backup_before_toggle.sql

# Or manually remove column
psql luffy -c "ALTER TABLE services DROP COLUMN IF EXISTS log_processing_enabled;"
```

## Benefits

### 1. User Control
- Users can pause/resume processing without code changes
- No need to restart services
- Immediate effect

### 2. Resource Optimization
- Save resources by disabling processing for low-priority services
- Reduce OpenSearch/Elasticsearch query load
- Lower processing costs

### 3. Operational Flexibility
- Pause during maintenance windows
- Disable for testing/development
- Quick response to issues

### 4. Simplified Architecture
- No scheduled RCA/indexing (on-demand only)
- Cleaner task configuration
- Easier to understand and maintain

## Future Enhancements

### 1. Schedule-Based Toggle
```json
{
  "log_processing_schedule": {
    "enabled": true,
    "business_hours_only": true,
    "timezone": "America/New_York",
    "exclude_weekends": true
  }
}
```

### 2. Auto-Disable on Errors
```json
{
  "auto_disable_on_errors": true,
  "error_threshold": 5,
  "error_window_minutes": 10
}
```

### 3. Gradual Rollout
```json
{
  "processing_percentage": 50,  // Process 50% of logs
  "sampling_strategy": "random"
}
```

## Summary

The log processing toggle provides:
- ✅ UI-controlled processing flow
- ✅ Per-service enable/disable
- ✅ No scheduled RCA/indexing (manual only)
- ✅ Backward compatible (default enabled)
- ✅ Immediate effect (no restart needed)
- ✅ Resource optimization
- ✅ Operational flexibility

**Result: Users have full control over log processing through a simple toggle, while RCA and code indexing are available on-demand.**
