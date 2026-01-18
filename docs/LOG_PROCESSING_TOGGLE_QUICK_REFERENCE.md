# Log Processing Toggle - Quick Reference

## TL;DR

- ✅ **Log Processing**: UI toggle in Dashboard (enable/disable per service)
- ❌ **RCA Generation**: Manual trigger only (no scheduling)
- ❌ **Code Indexing**: Manual trigger only (no scheduling)

## Setup (3 steps)

```bash
# 1. Run migration
python scripts/migrate_log_processing_toggle.py

# 2. Restart backend
uvicorn src.services.api:app --reload

# 3. Restart Celery
celery -A src.services.tasks worker --loglevel=info
celery -A src.services.tasks beat --loglevel=info
```

## UI Usage

### Dashboard Toggle

1. Go to Dashboard
2. Select service from dropdown
3. See toggle in header: **Log Processing: [▶/⏸]**
4. Click to enable/disable
5. See success message

### Toggle States

| State | Icon | Meaning |
|-------|------|---------|
| Enabled | ▶ | Processing active |
| Disabled | ⏸ | Processing paused |
| Loading | ⏳ | Updating... |

## API Usage

### Enable Processing

```bash
curl -X POST "http://localhost:8000/api/v1/services/web-app/toggle-log-processing?enabled=true"
```

### Disable Processing

```bash
curl -X POST "http://localhost:8000/api/v1/services/web-app/toggle-log-processing?enabled=false"
```

### Check Status

```bash
curl "http://localhost:8000/api/v1/services/web-app/config" | jq '.log_processing_enabled'
```

## Manual Triggers

### Trigger Log Fetch

```bash
curl -X POST "http://localhost:8000/api/v1/services/web-app/trigger-log-fetch"
```

### Trigger RCA

```bash
curl -X POST "http://localhost:8000/api/v1/services/web-app/trigger-rca"
```

### Trigger Code Indexing

```bash
curl -X POST "http://localhost:8000/api/v1/services/web-app/trigger-code-indexing"
```

## What Changed

### Removed ❌

- RCA scheduling (was every 15 minutes)
- Code indexing scheduling (was daily at 2 AM)

### Added ✅

- Log processing toggle per service
- UI control in Dashboard
- API endpoint for toggle

### Kept ✅

- Log fetching schedule (respects toggle)
- Manual triggers for all tasks
- Cleanup task (weekly)

## Behavior

### When ENABLED (Default)

✅ Logs fetched on schedule
✅ Exceptions extracted
✅ Clustering happens
✅ Notifications sent
✅ RCA available (manual)
✅ Indexing available (manual)

### When DISABLED

❌ No log fetching
❌ No exception extraction
❌ No clustering
❌ No notifications
✅ RCA still available (manual)
✅ Indexing still available (manual)
✅ Existing data accessible

## Common Use Cases

### Maintenance Window

```bash
# Disable before maintenance
curl -X POST "http://localhost:8000/api/v1/services/web-app/toggle-log-processing?enabled=false"

# Re-enable after maintenance
curl -X POST "http://localhost:8000/api/v1/services/web-app/toggle-log-processing?enabled=true"
```

### Development Service

```bash
# Disable processing for dev service
curl -X POST "http://localhost:8000/api/v1/services/dev-api/toggle-log-processing?enabled=false"
```

### On-Demand RCA

```bash
# Trigger RCA for specific cluster
curl -X POST "http://localhost:8000/api/v1/rca/generate" \
  -H "Content-Type: application/json" \
  -d '{"cluster_id": "cluster-123"}'
```

## Verification

### Check Database

```bash
psql luffy -c "SELECT id, name, log_processing_enabled FROM services;"
```

### Check Logs

```bash
# When disabled, you'll see:
tail -f celery_worker.log | grep "Log processing disabled"
```

### Check UI

1. Open http://localhost:3000/dashboard
2. Select service
3. See toggle in header

## Troubleshooting

### Toggle not appearing?

- ✅ Service selected?
- ✅ Page refreshed?
- ✅ Backend running?

### Toggle not working?

- ✅ Migration ran?
- ✅ Database updated?
- ✅ Celery running?

### Still processing when disabled?

- ⏳ Wait for next scheduled run
- 🔍 Check Celery logs
- ✅ Verify service status

## Quick Commands

```bash
# Enable all services
for service in web-app api-service; do
  curl -X POST "http://localhost:8000/api/v1/services/$service/toggle-log-processing?enabled=true"
done

# Disable all services
for service in web-app api-service; do
  curl -X POST "http://localhost:8000/api/v1/services/$service/toggle-log-processing?enabled=false"
done

# Check all services
curl "http://localhost:8000/api/v1/services/status" | jq '.[] | {name, log_processing_enabled}'
```

## Key Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/services/{id}/toggle-log-processing` | Toggle processing |
| POST | `/services/{id}/trigger-log-fetch` | Manual log fetch |
| POST | `/services/{id}/trigger-rca` | Manual RCA |
| POST | `/services/{id}/trigger-code-indexing` | Manual indexing |
| GET | `/services/{id}/config` | Get config |
| GET | `/services/{id}/status` | Get status |

## Files Modified

**Backend (4):**
- `src/storage/models.py`
- `src/services/tasks.py`
- `src/services/api_service_config.py`
- `scripts/migrate_log_processing_toggle.py` (NEW)

**Frontend (3):**
- `frontend/src/api/client.ts`
- `frontend/src/types/index.ts`
- `frontend/src/pages/Dashboard.tsx`

## Documentation

- `docs/LOG_PROCESSING_TOGGLE.md` - Full documentation
- `docs/LOG_PROCESSING_TOGGLE_IMPLEMENTATION_SUMMARY.md` - Implementation details
- `docs/LOG_PROCESSING_TOGGLE_QUICK_REFERENCE.md` - This file

## Support

For issues or questions:
1. Check documentation
2. Verify setup steps
3. Check logs
4. Review troubleshooting section
