# Auto-Sync Migration Summary

## Overview

Successfully migrated the `auto_sync` functionality from the `CodeIndexer` class (local mode) to the `APICodeIndexer` class (API mode).

## Changes Made

### 1. **CodeIndexer Class** (`src/services/code_indexer.py`)

**Removed:**
- ❌ `auto_sync` parameter from `index_repository()` method
- ❌ `sync_repository()` method (entire method ~120 lines)
- ❌ Auto-sync logic from `index_repository()` method

**Rationale:**
- Local mode assumes the user manages the repository manually (git pull, git clone, etc.)
- Auto-sync was causing confusion as it tried to pull from remote, which may not always be desired
- Local mode is for scenarios where the repository is already cloned and managed externally

**Before:**
```python
def index_repository(self, languages: List[str] = None, force_full: bool = False, auto_sync: bool = True) -> Dict[str, int]:
    # Auto-sync logic
    if auto_sync:
        sync_result = self.sync_repository(auto_sync=True)
        # ... handle sync result
    # ... indexing logic
```

**After:**
```python
def index_repository(self, languages: List[str] = None, force_full: bool = False) -> Dict[str, int]:
    # Direct indexing without auto-sync
    # ... indexing logic
```

---

### 2. **APICodeIndexer Class** (`src/services/code_indexer_api.py`)

**Added:**
- ✅ `auto_sync` parameter to `index_repository()` method (default: `True`)
- ✅ `sync_repository()` method (~90 lines)
- ✅ Auto-sync logic in `index_repository()` method
- ✅ `sync_status` field in stats dictionary

**Rationale:**
- API mode fetches code from remote (GitHub/GitLab) via API
- Auto-sync makes perfect sense here as it checks for new commits on remote
- API mode is stateless - no local repository to manage
- Always fetches latest code from remote when auto_sync is enabled

**Implementation:**

```python
def index_repository(
    self,
    languages: List[str] = None,
    force_full: bool = False,
    auto_sync: bool = True  # NEW
) -> Dict[str, int]:
    """
    Index repository via API with automatic sync support
    
    Args:
        languages: List of languages to index (e.g., ['python', 'java'])
        force_full: Force full indexing even if incremental is possible
        auto_sync: Automatically sync (fetch latest commit) before indexing (default: True)
        
    Returns:
        Statistics dict with counts including sync_status
    """
    # Initialize stats with sync_status
    stats = {
        'files_indexed': 0,
        'code_blocks_created': 0,
        'errors': 0,
        'commit_sha': None,
        'sync_status': None  # NEW
    }
    
    # STEP 1: Sync repository with remote if auto_sync is enabled
    if auto_sync:
        logger.info("Auto-sync enabled, fetching latest commit from remote...")
        sync_result = self.sync_repository(auto_sync=True)
        stats['sync_status'] = sync_result
        
        # If changes were detected, force full indexing
        if sync_result.get('changes_detected'):
            logger.info("New commits detected on remote, forcing full indexing")
            force_full = True
    
    # ... rest of indexing logic
```

**New Method:**

```python
def sync_repository(self, auto_sync: bool = True) -> Dict[str, Any]:
    """
    Sync repository with remote by fetching latest commit SHA.
    For API-based indexing, this checks if there are new commits on the remote.
    
    Returns:
        Dictionary with sync status and details:
        {
            'synced': bool,
            'before_commit': str,
            'after_commit': str,
            'changes_detected': bool,
            'error': str or None
        }
    """
    # Fetch latest commit from GitHub/GitLab API
    # Compare with last indexed commit
    # Return sync status
```

---

### 3. **Tasks** (`src/services/tasks.py`)

**Updated:**
- ✅ Swapped auto_sync logic: API indexer now receives `auto_sync`, local indexer doesn't

**Before:**
```python
if isinstance(indexer.__class__.__name__, str) and 'API' in indexer.__class__.__name__:
    # API indexer - no auto_sync parameter
    stats = indexer.index_repository(
        languages=['python', 'java'],
        force_full=force_full
    )
else:
    # Local indexer - supports auto_sync
    stats = indexer.index_repository(
        languages=['python', 'java'],
        force_full=force_full,
        auto_sync=auto_sync
    )
```

**After:**
```python
if isinstance(indexer.__class__.__name__, str) and 'API' in indexer.__class__.__name__:
    # API indexer - supports auto_sync (fetches latest commit from remote)
    stats = indexer.index_repository(
        languages=['python', 'java'],
        force_full=force_full,
        auto_sync=auto_sync
    )
else:
    # Local indexer - no longer supports auto_sync (removed)
    stats = indexer.index_repository(
        languages=['python', 'java'],
        force_full=force_full
    )
```

---

## Behavior Changes

### Local Mode (CodeIndexer)

**Before:**
- ✅ Attempted to `git pull` from remote before indexing
- ✅ Could fail if uncommitted changes exist
- ✅ Required Git repository with remote origin

**After:**
- ✅ No automatic git operations
- ✅ User manages repository manually (git pull, git clone, etc.)
- ✅ Simpler, more predictable behavior
- ✅ No dependency on remote origin

### API Mode (APICodeIndexer)

**Before:**
- ❌ No auto-sync support
- ❌ Always fetched latest commit
- ❌ No sync status reporting

**After:**
- ✅ Auto-sync enabled by default
- ✅ Checks for new commits on remote
- ✅ Forces full indexing if new commits detected
- ✅ Reports sync status in response
- ✅ Can be disabled with `auto_sync=False`

---

## API Changes

### Endpoint: `POST /api/v1/code-indexing/services/{service_id}/trigger`

**Parameters:**
- `force_full` (bool, default: False) - Force full indexing
- `auto_sync` (bool, default: True) - **Now applies to API mode only**

**Response (API Mode):**
```json
{
  "status": "success",
  "stats": {
    "files_indexed": 150,
    "code_blocks_created": 1200,
    "errors": 0,
    "commit_sha": "abc123def456",
    "sync_status": {
      "synced": true,
      "before_commit": "xyz789abc012",
      "after_commit": "abc123def456",
      "changes_detected": true,
      "error": null
    }
  }
}
```

**Response (Local Mode):**
```json
{
  "status": "success",
  "stats": {
    "total_files": 150,
    "total_blocks": 1200,
    "errors": 0,
    "mode": "incremental"
  }
}
```

---

## Migration Guide

### For Users Using Local Mode

**No action required.** The local indexer will continue to work as before, but without automatic git pull. You should manually run `git pull` before triggering indexing if you want the latest code.

**Recommended workflow:**
```bash
# 1. Update repository manually
cd /path/to/repo
git pull origin main

# 2. Trigger indexing
curl -X POST "http://localhost:8000/api/v1/code-indexing/services/my-service/trigger"
```

### For Users Using API Mode

**No action required.** Auto-sync is enabled by default and will automatically fetch the latest commit from GitHub/GitLab before indexing.

**To disable auto-sync:**
```bash
curl -X POST "http://localhost:8000/api/v1/code-indexing/services/my-service/trigger?auto_sync=false"
```

---

## Benefits

### Local Mode
- ✅ **Simpler logic**: No git operations, just indexing
- ✅ **More predictable**: User has full control over repository state
- ✅ **Fewer errors**: No failures due to uncommitted changes or diverged branches
- ✅ **Faster**: No git pull overhead

### API Mode
- ✅ **Always up-to-date**: Automatically fetches latest commits
- ✅ **Smart indexing**: Forces full indexing when new commits detected
- ✅ **Status reporting**: Detailed sync status in response
- ✅ **Configurable**: Can disable auto-sync if needed
- ✅ **No local repository**: Stateless, works entirely via API

---

## Testing

### Test Local Mode
```bash
# Should work without auto_sync parameter
curl -X POST "http://localhost:8000/api/v1/code-indexing/services/local-service/trigger"
```

### Test API Mode with Auto-Sync
```bash
# Should fetch latest commit and index
curl -X POST "http://localhost:8000/api/v1/code-indexing/services/api-service/trigger?auto_sync=true"
```

### Test API Mode without Auto-Sync
```bash
# Should use current commit without checking remote
curl -X POST "http://localhost:8000/api/v1/code-indexing/services/api-service/trigger?auto_sync=false"
```

---

## Files Modified

1. **src/services/code_indexer.py**
   - Removed `auto_sync` parameter from `index_repository()`
   - Removed `sync_repository()` method
   - Simplified indexing logic

2. **src/services/code_indexer_api.py**
   - Added `auto_sync` parameter to `index_repository()`
   - Added `sync_repository()` method
   - Added sync logic to `index_repository()`
   - Added `sync_status` to stats response

3. **src/services/tasks.py**
   - Swapped auto_sync logic between API and local indexers
   - Updated comments to reflect new behavior

---

## Summary

The auto-sync functionality has been successfully migrated from the local `CodeIndexer` class to the API `APICodeIndexer` class, where it makes more architectural sense. This change:

- **Simplifies local mode**: No automatic git operations, user manages repository
- **Enhances API mode**: Automatic sync with remote, smart indexing, status reporting
- **Improves clarity**: Each mode has clear responsibilities
- **Maintains compatibility**: Existing workflows continue to work with minimal changes

**Result: Better separation of concerns and more intuitive behavior for both local and API-based code indexing!**
