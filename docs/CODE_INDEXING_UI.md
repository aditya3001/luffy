# Code Indexing UI - User Guide

## 📋 Overview

The Code Indexing UI provides a comprehensive interface for managing on-demand code indexing for your services. Access it through the **Settings** page after selecting a service.

---

## 🎯 Features

### 1. **Real-Time Status Monitoring**
- View current indexing status (Not Indexed, Indexing, Completed, Failed)
- See last indexed timestamp
- Track Git commit SHA of indexed code
- View indexing trigger reason (exception_detected, manual, etc.)

### 2. **Manual Trigger Control**
- Trigger incremental indexing (fast, only changed files)
- Force full re-indexing (slower, complete index)
- Confirmation dialog with options
- Real-time task tracking

### 3. **Enable/Disable Auto-Indexing**
- Toggle automatic indexing on exception detection
- Confirmation for disabling
- Visual status indicators

### 4. **Indexing History**
- View past 5 indexing operations
- See files and blocks indexed
- Track indexing mode (full vs incremental)
- Commit SHA for each operation

### 5. **Service Information**
- Repository path and branch
- Git configuration
- Current status

---

## 🚀 How to Use

### Accessing Code Indexing Control

1. **Navigate to Settings:**
   - Click **Settings** in the sidebar navigation
   
2. **Select a Service:**
   - Choose a service from the header dropdown
   - The Code Indexing Control panel will appear

### Triggering Manual Indexing

**Incremental Indexing (Recommended):**
1. Click **"Trigger Indexing"** button
2. Leave "Force full re-indexing" unchecked
3. Click **"Incremental Index"**
4. Wait for completion (usually 10-30 seconds)

**Full Re-Indexing:**
1. Click **"Trigger Indexing"** button
2. Check **"Force full re-indexing"** checkbox
3. Click **"Full Re-Index"**
4. Wait for completion (may take 1-5 minutes)

### Enabling/Disabling Auto-Indexing

**To Disable:**
1. Click **"Disable Auto-Indexing"** button
2. Confirm in the dialog
3. Status changes to "Disabled"

**To Enable:**
1. Click **"Enable Auto-Indexing"** button
2. Status changes to "Enabled"

### Viewing Indexing History

1. Click **"View History"** button
2. Modal opens showing last 5 indexing operations
3. Review details:
   - Indexed timestamp
   - Commit SHA
   - Files and blocks indexed
   - Indexing mode (full/incremental)

---

## 📊 Status Indicators

### Indexing Status Tags

| Status | Color | Icon | Meaning |
|--------|-------|------|---------|
| **Not Indexed** | Gray | 🕐 | Code has never been indexed |
| **Indexing...** | Blue | ⏳ | Indexing in progress |
| **Completed** | Green | ✅ | Successfully indexed |
| **Failed** | Red | ❌ | Indexing failed (see error) |

### Auto-Indexing Status

| Status | Color | Meaning |
|--------|-------|---------|
| **Enabled** | Green | Auto-indexing on exception detection is active |
| **Disabled** | Gray | Auto-indexing is turned off |

---

## 🎨 UI Components

### Main Card

```
┌─────────────────────────────────────────────────────┐
│ 🔧 Code Indexing Control        [Enabled] [✅ Completed] │
├─────────────────────────────────────────────────────┤
│                                                     │
│ Service: Web Application                            │
│ Repository: /path/to/repo                           │
│ Branch: main                                        │
│                                                     │
│ Indexing Status                                     │
│ Last Indexed: 2025-12-07 14:30:00                  │
│ Commit: abc123de                                    │
│ Last Trigger: exception_detected                    │
│                                                     │
│ [🔄 Trigger Indexing] [Disable Auto-Indexing] [📜 View History] │
│                                                     │
│ ℹ️ On-Demand Indexing                               │
│ Code indexing is triggered automatically when       │
│ exceptions are detected. You can also trigger it    │
│ manually using the button above.                    │
│                                                     │
│ • Incremental indexing only processes changed files │
│ • Full re-indexing processes all files              │
│ • Minimum 5-minute interval between operations      │
└─────────────────────────────────────────────────────┘
```

### Trigger Dialog

```
┌─────────────────────────────────────────┐
│ Trigger Code Indexing                   │
├─────────────────────────────────────────┤
│                                         │
│ This will trigger code indexing for     │
│ Web Application.                        │
│                                         │
│ ☐ Force full re-indexing (slower, but  │
│   ensures complete index)               │
│                                         │
│ ℹ️ Incremental indexing will only       │
│   process changed files since last      │
│   index                                 │
│                                         │
│         [Cancel] [Incremental Index]    │
└─────────────────────────────────────────┘
```

### History Modal

```
┌─────────────────────────────────────────────────────┐
│ 📜 Indexing History                                  │
├─────────────────────────────────────────────────────┤
│                                                     │
│ ┌─────────────────────────────────────────────┐   │
│ │ Repository: web-app                         │   │
│ │ Indexed At: 2025-12-07 14:30:00            │   │
│ │ Commit: abc123de                            │   │
│ │ Files: 45    Blocks: 234                    │   │
│ │ Mode: incremental                           │   │
│ └─────────────────────────────────────────────┘   │
│                                                     │
│ ┌─────────────────────────────────────────────┐   │
│ │ Repository: web-app                         │   │
│ │ Indexed At: 2025-12-07 10:15:00            │   │
│ │ Commit: def456ab                            │   │
│ │ Files: 120   Blocks: 678                    │   │
│ │ Mode: full                                  │   │
│ └─────────────────────────────────────────────┘   │
│                                                     │
│                                    [Close]          │
└─────────────────────────────────────────────────────┘
```

---

## ⚙️ Configuration

### Service Requirements

To use code indexing, your service must have:

1. **Git Repository Path** configured
2. **Git Branch** specified (default: main)
3. **Code Indexing Enabled** flag set to true

### Setting Up a Service

1. Go to **Services** page
2. Create or edit a service
3. Fill in:
   - Repository URL: `https://github.com/org/repo`
   - Git Branch: `main` (or your branch)
   - Git Repo Path: `/path/to/local/clone`
4. Save the service

---

## 🔔 Notifications & Feedback

### Success Messages

- **"Code indexing triggered successfully! Task ID: abc-123"**
  - Indexing has started
  - Task ID for tracking
  
- **"Code indexing enabled"**
  - Auto-indexing is now active

### Warning Messages

- **"Code indexing disabled"**
  - Auto-indexing has been turned off

### Error Messages

- **"No Git repository configured for this service"**
  - Action: Configure repository in service settings
  
- **"Code indexing already in progress for this service"**
  - Action: Wait for current indexing to complete
  
- **"Failed to trigger code indexing"**
  - Action: Check service configuration and try again

---

## 🎯 Use Cases

### Use Case 1: First-Time Setup

**Scenario:** New service with no code indexed

**Steps:**
1. Select service from header
2. Go to Settings page
3. Verify repository configuration
4. Click "Trigger Indexing"
5. Choose "Full Re-Index" (first time)
6. Wait for completion
7. Verify status shows "Completed"

### Use Case 2: After Code Changes

**Scenario:** You've pushed new code and want to update the index

**Steps:**
1. Select service
2. Go to Settings
3. Click "Trigger Indexing"
4. Choose "Incremental Index" (faster)
5. Wait for completion
6. Verify new commit SHA

### Use Case 3: Troubleshooting Failed Indexing

**Scenario:** Indexing status shows "Failed"

**Steps:**
1. Check error message in red alert
2. Common issues:
   - Repository path incorrect
   - Branch doesn't exist
   - Git permissions issue
3. Fix the issue in service configuration
4. Click "Trigger Indexing" again
5. Monitor status

### Use Case 4: Disabling for Maintenance

**Scenario:** Temporarily disable auto-indexing during maintenance

**Steps:**
1. Select service
2. Go to Settings
3. Click "Disable Auto-Indexing"
4. Confirm
5. Perform maintenance
6. Click "Enable Auto-Indexing" when done

---

## 📈 Best Practices

### 1. **Use Incremental Indexing**
- Faster (10-30 seconds vs 1-5 minutes)
- Only processes changed files
- Sufficient for most cases

### 2. **Force Full Re-Index When:**
- First time indexing a service
- After major refactoring
- If incremental indexing fails
- Repository structure changed significantly

### 3. **Monitor Indexing Status**
- Check status after triggering
- Review error messages if failed
- Verify commit SHA matches your code

### 4. **Keep Auto-Indexing Enabled**
- Ensures code is indexed when exceptions occur
- Provides fresh context for RCA
- No manual intervention needed

### 5. **Review Indexing History**
- Track indexing frequency
- Identify patterns
- Verify coverage

---

## 🔧 Technical Details

### API Endpoints Used

```typescript
// Trigger indexing
POST /api/v1/code-indexing/services/{service_id}/trigger?force_full=false

// Get status
GET /api/v1/code-indexing/services/{service_id}/status

// Get history
GET /api/v1/code-indexing/services/{service_id}/history?limit=5

// Enable/Disable
POST /api/v1/code-indexing/services/{service_id}/enable
POST /api/v1/code-indexing/services/{service_id}/disable
```

### Auto-Refresh

- Status refreshes every **10 seconds**
- Shows real-time indexing progress
- Updates automatically when indexing completes

### Minimum Interval

- **5 minutes** between indexing operations
- Prevents spam and resource exhaustion
- Enforced at backend level

---

## 🐛 Troubleshooting

### Issue: "Trigger Indexing" Button Disabled

**Possible Causes:**
- No Git repository configured
- Indexing already in progress
- Service not selected

**Solution:**
1. Check service configuration
2. Wait for current indexing to complete
3. Select a service from header

### Issue: Indexing Stuck on "Indexing..."

**Possible Causes:**
- Task crashed
- Network issue
- Repository too large

**Solution:**
1. Wait 5 minutes for timeout
2. Check Celery worker logs
3. Manually reset status (contact admin)
4. Try again with smaller repository

### Issue: Status Shows "Failed"

**Possible Causes:**
- Repository path incorrect
- Branch doesn't exist
- Git permissions denied
- Network connectivity

**Solution:**
1. Read error message
2. Verify repository configuration
3. Check Git access
4. Fix issue and retry

### Issue: History Shows No Records

**Possible Causes:**
- Service never indexed
- Database migration not run
- Different service selected

**Solution:**
1. Trigger indexing at least once
2. Check database migration status
3. Verify correct service selected

---

## 📱 Responsive Design

The Code Indexing UI is fully responsive:

- **Desktop (>1200px):** Full layout with all features
- **Tablet (768-1200px):** Stacked layout, all features visible
- **Mobile (<768px):** Vertical layout, scrollable

---

## ♿ Accessibility

- Keyboard navigation supported
- Screen reader friendly
- High contrast mode compatible
- Focus indicators visible
- ARIA labels on all interactive elements

---

## 🎨 Customization

### Theme Support

The UI respects your theme settings:
- **Light Mode:** Clean, bright interface
- **Dark Mode:** Eye-friendly dark colors

### Icon Legend

- 🔧 Code Indexing
- 🔄 Refresh/Sync
- ✅ Success/Completed
- ❌ Error/Failed
- 🕐 Pending/Not Started
- ⏳ In Progress
- 📜 History
- 🌿 Git Branch
- ℹ️ Information

---

## 📚 Related Documentation

- [On-Demand Code Indexing Guide](./ON_DEMAND_CODE_INDEXING.md)
- [Implementation Summary](./ON_DEMAND_INDEXING_IMPLEMENTATION.md)
- [Code Indexing Architecture](./CODE_INDEXING_GUIDE.md)
- [API Reference](./API_REFERENCE.md)

---

## 🆘 Support

If you encounter issues:

1. Check this documentation
2. Review error messages
3. Check service configuration
4. Contact your system administrator
5. File a bug report with:
   - Service ID
   - Error message
   - Steps to reproduce
   - Screenshots (if applicable)

---

## ✅ Quick Reference

### Common Actions

| Action | Steps |
|--------|-------|
| **Trigger Incremental Index** | Settings → Trigger Indexing → Incremental Index |
| **Trigger Full Re-Index** | Settings → Trigger Indexing → ✓ Force full → Full Re-Index |
| **View Status** | Settings → Check status tags |
| **View History** | Settings → View History |
| **Enable Auto-Index** | Settings → Enable Auto-Indexing |
| **Disable Auto-Index** | Settings → Disable Auto-Indexing |

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Enter` | Confirm dialog |
| `Esc` | Close modal/dialog |
| `Tab` | Navigate between fields |
| `Space` | Toggle checkbox |

---

**Last Updated:** 2025-12-07  
**Version:** 1.0.0  
**Component:** CodeIndexingControl.tsx
