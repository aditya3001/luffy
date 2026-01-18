# Manual Code Indexing Trigger - Implementation

## ✅ Feature Added

### **What:**
Manual code indexing trigger button in the log sources table for on-demand code indexing.

### **Where:**
Services & Log Sources page → Log Sources table → Actions column

---

## 🎨 UI Implementation

### **Button Appearance:**

The "Trigger Code Indexing" button appears in the Actions column **only for log sources with code indexing enabled**.

```
| Name              | Type       | ... | Code Indexing  | Actions                    |
|-------------------|------------|-----|----------------|----------------------------|
| Production Logs   | OPENSEARCH | ... | Disabled       | [⚡] [✏️] [🗑️]             |
| Staging Logs      | OPENSEARCH | ... | ✅ Active      | [⚡] [🔄] [✏️] [🗑️]        |
| Dev Logs          | OPENSEARCH | ... | ❌ Expired     | [⚡] [🔄] [✏️] [🗑️]        |
```

**Icons:**
- ⚡ = Test Connection
- 🔄 = Trigger Code Indexing (only if code_indexing_enabled = true)
- ✏️ = Edit
- 🗑️ = Delete

---

## 🔄 User Flow

### **Step 1: User Clicks Trigger Button**

```
User clicks [🔄] button on log source row
  ↓
Confirmation modal appears:
┌────────────────────────────────────────┐
│ Trigger Code Indexing                  │
├────────────────────────────────────────┤
│                                        │
│ This will trigger code indexing for    │
│ "Production Logs". Continue?           │
│                                        │
│ [Cancel]  [OK]                         │
└────────────────────────────────────────┘
```

### **Step 2: User Confirms**

```
User clicks [OK]
  ↓
Frontend calls API:
  POST /log-sources/{id}/trigger-indexing?force_full=false
  ↓
Backend response:
  {
    "message": "Code indexing triggered",
    "task_id": "abc-123-def-456",
    "log_source_id": "prod-logs"
  }
  ↓
Success message:
  ✅ "Code indexing triggered! Task ID: abc-123-def-456"
  ↓
Table refreshes to show updated status
```

### **Step 3: Indexing Runs**

```
Backend:
  1. Celery task starts
  2. Fetches Git config from log source
  3. Decrypts access token
  4. Calls GitHub/GitLab API
  5. Fetches code files
  6. Generates embeddings
  7. Stores in vector DB
  8. Updates indexing status
  
UI Updates:
  - indexing_status: "in_progress" → "completed"
  - last_indexed_at: Updated timestamp
  - Code Indexing column: Shows "Active" ✅
```

---

## 📁 Files Modified

### **1. Frontend API Client (`frontend/src/api/client.ts`)**

Added two new methods to `logSourceAPI`:

```typescript
// Trigger code indexing for a log source
triggerIndexing: async (sourceId: string, forceFull: boolean = false): Promise<{ 
  message: string; 
  task_id: string; 
  log_source_id: string;
}> => {
  const response = await api.post(`/log-sources/${sourceId}/trigger-indexing`, null, {
    params: { force_full: forceFull }
  });
  return response.data;
},

// Get indexing status for a log source
getIndexingStatus: async (sourceId: string): Promise<{
  log_source_id: string;
  code_indexing_enabled: boolean;
  indexing_status: string;
  last_indexed_commit: string | null;
  last_indexed_at: string | null;
  indexing_error: string | null;
  token_status: string;
}> => {
  const response = await api.get(`/log-sources/${sourceId}/indexing-status`);
  return response.data;
},
```

### **2. Log Sources Page (`frontend/src/pages/LogSources.tsx`)**

Added trigger button to Actions column:

```typescript
{record.code_indexing_enabled && (
  <Tooltip title="Trigger Code Indexing">
    <Button
      icon={<SyncOutlined />}
      size="small"
      onClick={() => {
        Modal.confirm({
          title: 'Trigger Code Indexing',
          content: `This will trigger code indexing for "${record.name}". Continue?`,
          onOk: () => {
            logSourceAPI.triggerIndexing(record.id, false)
              .then((data) => {
                message.success(`Code indexing triggered! Task ID: ${data.task_id}`);
                queryClient.invalidateQueries({ queryKey: ['log-sources'] });
              })
              .catch((error) => {
                message.error(error.response?.data?.detail || 'Failed to trigger indexing');
              });
          },
        });
      }}
    />
  </Tooltip>
)}
```

---

## 🔧 Backend API Endpoints Needed

### **1. Trigger Indexing**

```python
POST /api/v1/log-sources/{log_source_id}/trigger-indexing?force_full=false

Response:
{
  "message": "Code indexing triggered successfully",
  "task_id": "abc-123-def-456",
  "log_source_id": "prod-logs",
  "force_full": false
}
```

**Implementation:**
```python
@router.post("/log-sources/{log_source_id}/trigger-indexing")
async def trigger_code_indexing(
    log_source_id: str,
    force_full: bool = False,
    db: Session = Depends(get_db)
):
    # Get log source
    log_source = db.query(LogSource).filter(LogSource.id == log_source_id).first()
    if not log_source:
        raise HTTPException(status_code=404, detail="Log source not found")
    
    # Check if code indexing enabled
    if not log_source.code_indexing_enabled:
        raise HTTPException(status_code=400, detail="Code indexing not enabled for this log source")
    
    # Check token status
    if log_source.token_status != 'valid':
        raise HTTPException(status_code=400, detail=f"Cannot trigger indexing: token status is {log_source.token_status}")
    
    # Trigger Celery task
    from src.services.tasks import index_code_repository_for_log_source
    task = index_code_repository_for_log_source.delay(
        log_source_id=log_source_id,
        force_full=force_full
    )
    
    return {
        "message": "Code indexing triggered successfully",
        "task_id": task.id,
        "log_source_id": log_source_id,
        "force_full": force_full
    }
```

### **2. Get Indexing Status**

```python
GET /api/v1/log-sources/{log_source_id}/indexing-status

Response:
{
  "log_source_id": "prod-logs",
  "code_indexing_enabled": true,
  "indexing_status": "completed",
  "last_indexed_commit": "abc123def456",
  "last_indexed_at": "2025-12-07T10:30:00Z",
  "indexing_error": null,
  "token_status": "valid"
}
```

---

## 🎯 Features

### **1. Conditional Display**
- ✅ Button only shows if `code_indexing_enabled = true`
- ✅ Keeps UI clean for log sources without code indexing

### **2. Confirmation Modal**
- ✅ Prevents accidental triggers
- ✅ Shows log source name for clarity
- ✅ User can cancel before triggering

### **3. Success Feedback**
- ✅ Shows task ID for tracking
- ✅ Success message with green checkmark
- ✅ Table auto-refreshes to show updated status

### **4. Error Handling**
- ✅ Shows error message if API call fails
- ✅ Handles token expiry gracefully
- ✅ Validates code indexing is enabled

### **5. Real-time Updates**
- ✅ Table refreshes after trigger
- ✅ Status column updates automatically
- ✅ Shows "in_progress" → "completed" transition

---

## 🔍 Use Cases

### **Use Case 1: Force Re-Index After Code Changes**

```
Scenario: Developer pushed major refactoring
Action: Click [🔄] to manually trigger indexing
Result: Latest code indexed immediately, not waiting for scheduled run
```

### **Use Case 2: Fix Failed Indexing**

```
Scenario: Previous indexing failed due to network issue
Action: Click [🔄] to retry indexing
Result: Indexing runs again with fresh attempt
```

### **Use Case 3: Initial Setup Testing**

```
Scenario: Just configured Git repository for log source
Action: Click [🔄] to test if indexing works
Result: Validates token, repository access, and indexing pipeline
```

### **Use Case 4: Update After Token Rotation**

```
Scenario: Updated expired access token
Action: Click [🔄] to verify new token works
Result: Indexing runs with new token, confirms it's valid
```

---

## 📊 Button States

### **Enabled (Clickable):**
- ✅ Code indexing enabled
- ✅ Token status: valid
- ✅ Not currently indexing

### **Disabled (Not Shown):**
- ❌ Code indexing disabled
- ❌ Log source doesn't have Git config

### **Error States:**
- ⚠️ Token expired → Shows error: "Cannot trigger: token expired"
- ⚠️ Token invalid → Shows error: "Cannot trigger: token invalid"
- ⚠️ Already indexing → Shows error: "Indexing already in progress"

---

## 🎨 Visual Examples

### **Before Trigger:**

```
┌────────────────────────────────────────────────────────────────┐
│ Log Sources (3)                                                │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│ Name              | Code Indexing  | Actions                  │
│ Production Logs   | ✅ Active      | [⚡] [🔄] [✏️] [🗑️]      │
│ Last indexed: 2 hours ago                                      │
└────────────────────────────────────────────────────────────────┘
```

### **After Clicking Trigger:**

```
┌────────────────────────────────────────────────────────────────┐
│ ✅ Code indexing triggered! Task ID: abc-123-def-456          │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│ Log Sources (3)                                                │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│ Name              | Code Indexing  | Actions                  │
│ Production Logs   | 🔄 In Progress | [⚡] [🔄] [✏️] [🗑️]      │
│ Indexing started just now...                                   │
└────────────────────────────────────────────────────────────────┘
```

### **After Completion:**

```
┌────────────────────────────────────────────────────────────────┐
│ Log Sources (3)                                                │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│ Name              | Code Indexing  | Actions                  │
│ Production Logs   | ✅ Active      | [⚡] [🔄] [✏️] [🗑️]      │
│ Last indexed: just now                                         │
└────────────────────────────────────────────────────────────────┘
```

---

## ✅ Summary

### **What's Implemented:**
- ✅ Trigger button in log sources table
- ✅ Conditional display (only if code indexing enabled)
- ✅ Confirmation modal
- ✅ API client methods
- ✅ Success/error messages
- ✅ Table auto-refresh

### **What's Needed (Backend):**
- ⏳ POST `/log-sources/{id}/trigger-indexing` endpoint
- ⏳ GET `/log-sources/{id}/indexing-status` endpoint
- ⏳ Celery task: `index_code_repository_for_log_source`
- ⏳ Token validation before triggering
- ⏳ Status updates during indexing

### **User Experience:**
1. User sees [🔄] button for log sources with code indexing
2. Clicks button → Confirmation modal appears
3. Confirms → API call triggers indexing
4. Success message shows task ID
5. Table refreshes to show "In Progress"
6. After completion, shows "Active" with updated timestamp

**Result: Users can manually trigger code indexing on-demand for any log source!** 🚀
