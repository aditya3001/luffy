# Log Processing Toggle - Implementation Summary

## ✅ Implementation Complete

Successfully implemented UI-controlled log processing toggle with removal of RCA and code indexing scheduling.

## 🎯 Changes Made

### 1. Removed Scheduled Tasks ❌

**Before:**
- RCA generation: Scheduled every 15 minutes
- Code indexing: Scheduled daily at 2 AM

**After:**
- RCA generation: Manual trigger only (on-demand)
- Code indexing: Manual trigger only (on-demand)
- Log processing: Scheduled but respects toggle

**File Modified:** `src/services/tasks.py`
- Removed RCA scheduling from `setup_periodic_tasks()`
- Removed code indexing scheduling from `setup_periodic_tasks()`
- Kept log fetching (respects toggle)
- Kept cleanup task (weekly)

### 2. Added Log Processing Toggle ✅

**Database Model:**
- Added `log_processing_enabled` field to Service model
- Type: `Boolean`
- Default: `TRUE` (backward compatible)

**File Modified:** `src/storage/models.py`

```python
# Processing Configuration
log_processing_enabled = Column(Boolean, default=True)  # Master toggle
```

### 3. Updated Task Logic ✅

**File Modified:** `src/services/tasks.py`

Added check in `fetch_and_process_logs()`:

```python
# Check if log processing is enabled for this service
service = db.query(Service).filter(Service.id == log_source.service_id).first()
if not service.log_processing_enabled:
    logger.info(f"Log processing disabled for service {service.name}, skipping")
    continue
```

### 4. Created API Endpoint ✅

**File Modified:** `src/services/api_service_config.py`

**New Endpoint:**
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

### 5. Updated API Models ✅

**File Modified:** `src/services/api_service_config.py`

Added `log_processing_enabled` to:
- `ServiceConfigRequest` model
- `ServiceConfigResponse` model

### 6. Created Migration Script ✅

**File Created:** `scripts/migrate_log_processing_toggle.py`

Features:
- Adds `log_processing_enabled` column
- Sets all existing services to enabled (backward compatible)
- Provides migration summary
- Includes rollback instructions

### 7. Updated Frontend API Client ✅

**File Modified:** `frontend/src/api/client.ts`

Added method to `servicesAPI`:

```typescript
toggleLogProcessing: async (serviceId: string, enabled: boolean) => {
  const response = await api.post(
    `/services/${serviceId}/toggle-log-processing?enabled=${enabled}`
  );
  return response.data;
}
```

### 8. Updated TypeScript Types ✅

**File Modified:** `frontend/src/types/index.ts`

Added to `Service` interface:

```typescript
// Processing Configuration
log_processing_enabled?: boolean;
```

### 9. Added UI Toggle to Dashboard ✅

**File Modified:** `frontend/src/pages/Dashboard.tsx`

**Features:**
- Toggle switch in Dashboard header
- Shows current processing status
- Play/Pause icons
- Loading state during API call
- Success/error messages
- Auto-refresh every 10 seconds

**UI Layout:**
```
Dashboard | [Time Range ▼] [Log Processing 🔄] [Monitoring 🔄] [Refresh 🔄]
```

**Implementation:**
```typescript
// Query for current service
const { data: currentService } = useQuery({
  queryKey: ['service', selectedService],
  queryFn: () => selectedService ? servicesAPI.get(selectedService) : null,
  enabled: !!selectedService,
  refetchInterval: 10000,
});

// Mutation for toggle
const toggleLogProcessingMutation = useMutation({
  mutationFn: (enabled: boolean) => 
    servicesAPI.toggleLogProcessing(selectedService!, enabled),
  onSuccess: (data) => {
    queryClient.invalidateQueries({ queryKey: ['service', selectedService] });
    message.success(data.message);
  },
});

// UI Component
<Switch
  checked={currentService?.log_processing_enabled ?? true}
  onChange={(checked) => toggleLogProcessingMutation.mutate(checked)}
  checkedChildren={<PlayCircleOutlined />}
  unCheckedChildren={<PauseCircleOutlined />}
  loading={toggleLogProcessingMutation.isPending}
/>
```

### 10. Created Documentation ✅

**Files Created:**
1. `docs/LOG_PROCESSING_TOGGLE.md` - Complete feature documentation
2. `docs/LOG_PROCESSING_TOGGLE_IMPLEMENTATION_SUMMARY.md` - This file

## 📊 Files Modified Summary

### Backend (4 files):
1. ✅ `src/storage/models.py` - Added log_processing_enabled field
2. ✅ `src/services/tasks.py` - Removed scheduling, added toggle check
3. ✅ `src/services/api_service_config.py` - Added toggle endpoint and models
4. ✅ `scripts/migrate_log_processing_toggle.py` - NEW migration script

### Frontend (3 files):
5. ✅ `frontend/src/api/client.ts` - Added toggleLogProcessing method
6. ✅ `frontend/src/types/index.ts` - Added log_processing_enabled to Service
7. ✅ `frontend/src/pages/Dashboard.tsx` - Added toggle UI

### Documentation (2 files):
8. ✅ `docs/LOG_PROCESSING_TOGGLE.md` - Feature documentation
9. ✅ `docs/LOG_PROCESSING_TOGGLE_IMPLEMENTATION_SUMMARY.md` - This summary

**Total: 9 files (4 backend, 3 frontend, 2 docs)**

## 🚀 Setup Instructions

### 1. Run Migration

```bash
cd /Users/rahularagi/PycharmProjects/CascadeProjects/luffy
python scripts/migrate_log_processing_toggle.py
```

Expected output:
```
✅ Column added successfully
✅ Existing services updated
✅ Migration completed successfully!
```

### 2. Restart Backend

```bash
# Stop current server (Ctrl+C)

# Start backend
uvicorn src.services.api:app --reload
```

### 3. Restart Celery Services

```bash
# Stop current workers (Ctrl+C)

# Start Celery worker
celery -A src.services.tasks worker --loglevel=info

# Start Celery beat (in separate terminal)
celery -A src.services.tasks beat --loglevel=info
```

### 4. Restart Frontend (if running)

```bash
cd frontend
npm run dev
```

## 🎯 Usage

### Via UI (Dashboard):

1. Navigate to Dashboard
2. Select a service from header dropdown
3. See "Log Processing" toggle in header
4. Click toggle to enable/disable
5. See success message
6. Processing starts/stops on next scheduled run

### Via API:

```bash
# Enable log processing
curl -X POST "http://localhost:8000/api/v1/services/web-app/toggle-log-processing?enabled=true"

# Disable log processing
curl -X POST "http://localhost:8000/api/v1/services/web-app/toggle-log-processing?enabled=false"

# Check status
curl "http://localhost:8000/api/v1/services/web-app/config" | jq '.log_processing_enabled'
```

## 🔍 Verification

### 1. Check Database

```bash
psql luffy -c "SELECT id, name, log_processing_enabled FROM services;"
```

Expected output:
```
     id      |       name        | log_processing_enabled 
-------------+-------------------+------------------------
 web-app     | Web Application   | t
 api-service | API Service       | t
```

### 2. Check API

```bash
curl "http://localhost:8000/api/v1/services/web-app/config"
```

Should include:
```json
{
  "log_processing_enabled": true,
  ...
}
```

### 3. Check UI

1. Open http://localhost:3000/dashboard
2. Select a service
3. See toggle switches in header:
   - Time Range dropdown
   - **Log Processing toggle** ← NEW
   - Monitoring toggle
   - Refresh button

### 4. Test Toggle

1. Click Log Processing toggle to disable
2. See success message: "Log processing disabled for service Web Application"
3. Check Celery logs - next run should skip this service:
   ```
   [INFO] Log processing disabled for service Web Application, skipping
   ```

## 📋 Behavior Summary

### When Log Processing is ENABLED (Default):

✅ Periodic log fetch runs normally
✅ Logs are fetched from OpenSearch/Elasticsearch
✅ Exceptions are extracted and clustered
✅ Notifications are sent
✅ RCA can be triggered manually
✅ Code indexing can be triggered manually

### When Log Processing is DISABLED:

❌ Periodic log fetch skips this service
❌ No logs are fetched
❌ No exceptions are extracted
❌ No clustering happens
✅ RCA can still be triggered manually for existing clusters
✅ Code indexing can still be triggered manually
✅ Existing data remains accessible
✅ UI remains functional

## 🎨 UI Screenshots

### Dashboard Header (Service Selected):

```
┌─────────────────────────────────────────────────────────────────┐
│ Dashboard                                                        │
│                                                                  │
│ [Time Range: 24 hours ▼] [Log Processing: ⏸] [Monitoring: ▶]  │
│                                                      [Refresh 🔄]│
└─────────────────────────────────────────────────────────────────┘
```

### Toggle States:

**Enabled (Playing):**
```
Log Processing: [▶ ON]
```

**Disabled (Paused):**
```
Log Processing: [⏸ OFF]
```

**Loading:**
```
Log Processing: [⏳ ...]
```

## 🔧 Troubleshooting

### Issue: Toggle not appearing

**Solution:**
1. Check if service is selected
2. Refresh page
3. Check browser console for errors
4. Verify backend is running

### Issue: Toggle not working

**Solution:**
1. Check backend logs for errors
2. Verify migration ran successfully
3. Check database column exists:
   ```bash
   psql luffy -c "\d services" | grep log_processing_enabled
   ```

### Issue: Processing still running when disabled

**Solution:**
1. Check service status:
   ```bash
   curl "http://localhost:8000/api/v1/services/web-app/config"
   ```
2. Verify Celery worker is running
3. Check Celery logs for skip message
4. Wait for next scheduled run (toggle doesn't stop current run)

## 📈 Benefits

### 1. User Control
- ✅ Enable/disable processing without code changes
- ✅ No service restart required
- ✅ Immediate effect on next run
- ✅ Per-service granularity

### 2. Resource Optimization
- ✅ Save resources for low-priority services
- ✅ Reduce OpenSearch query load
- ✅ Lower processing costs
- ✅ Flexible resource allocation

### 3. Operational Flexibility
- ✅ Pause during maintenance windows
- ✅ Disable for testing/development
- ✅ Quick response to issues
- ✅ No downtime required

### 4. Simplified Architecture
- ✅ No scheduled RCA (on-demand only)
- ✅ No scheduled indexing (on-demand only)
- ✅ Cleaner task configuration
- ✅ Easier to understand

## 🎯 Next Steps

### Optional Enhancements:

1. **Schedule-Based Toggle:**
   - Business hours only
   - Weekend exclusion
   - Timezone support

2. **Auto-Disable on Errors:**
   - Error threshold
   - Error window
   - Auto-recovery

3. **Processing Metrics:**
   - Logs processed count
   - Processing duration
   - Success/failure rate

4. **Notification on Toggle:**
   - Slack notification
   - Email notification
   - Webhook callback

## ✅ Checklist

- [x] Database model updated
- [x] Migration script created
- [x] Task logic updated
- [x] API endpoint created
- [x] API models updated
- [x] Frontend API client updated
- [x] TypeScript types updated
- [x] UI component added
- [x] Documentation created
- [x] Testing instructions provided

## 🎉 Summary

**Implementation Status:** ✅ COMPLETE

**Total Changes:**
- 4 backend files modified
- 3 frontend files modified
- 2 documentation files created
- 1 migration script created

**Key Features:**
- ✅ UI-controlled log processing toggle
- ✅ RCA and code indexing now on-demand only
- ✅ Per-service processing control
- ✅ Backward compatible (default enabled)
- ✅ No breaking changes
- ✅ Production ready

**Result:** Users can now control log processing through a simple toggle in the Dashboard UI, while RCA and code indexing are available on-demand through manual triggers.
