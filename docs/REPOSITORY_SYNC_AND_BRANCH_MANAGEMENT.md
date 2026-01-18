# Repository Sync and Branch Management for Code Indexing

## 📋 Overview

This document explains how Luffy syncs service repositories with their configured Git branches for code indexing, ensuring that the correct version of code is indexed for RCA generation.

---

## 🔄 How Repository Syncing Works

### 1. **Service Configuration**

Each service in Luffy has Git repository configuration stored in the database:

```python
# Service Model Fields
class Service:
    git_repo_path: str        # Local path to cloned repository
    git_branch: str           # Branch to index (e.g., 'main', 'develop', 'feature/xyz')
    repository_url: str       # Git repository URL (for reference)
    last_indexed_commit: str  # Last indexed commit SHA
```

**Example Configuration:**
```json
{
  "service_id": "web-app",
  "git_repo_path": "/repos/web-app",
  "git_branch": "main",
  "repository_url": "https://github.com/org/web-app"
}
```

---

### 2. **Repository Initialization**

When code indexing is triggered, the `CodeIndexer` class initializes with the service's repository configuration:

```python
# From tasks.py - index_code_repository task
if service_id:
    service = db.query(Service).filter(Service.id == service_id).first()
    repository_path = service.git_repo_path  # e.g., /repos/web-app
    branch = service.git_branch or 'main'    # e.g., main, develop
    
# Initialize CodeIndexer
indexer = CodeIndexer(
    repo_path=repository_path,  # /repos/web-app
    version=branch               # main
)
```

---

### 3. **Git Repository Access**

The `CodeIndexer` uses **GitPython** library to interact with the Git repository:

```python
# From code_indexer.py - __init__ method
def __init__(self, repo_path: str = None, version: str = None):
    self.repo_path = Path(repo_path or settings.git_repo_path)
    self.version = version or settings.code_version
    self.repo = None
    self.commit_sha = self._get_commit_sha()

def _get_commit_sha(self) -> str:
    """Get current commit SHA using GitPython"""
    if GIT_AVAILABLE:
        try:
            self.repo = git.Repo(self.repo_path)  # Open Git repository
            return self.repo.head.commit.hexsha   # Get current commit SHA
        except Exception as e:
            logger.error(f"Error accessing Git repository: {e}")
            return "unknown"
```

**What Happens:**
1. Opens the Git repository at `git_repo_path`
2. Reads the current HEAD commit SHA
3. Uses this SHA to track which version is being indexed

---

### 4. **Branch Checkout (Manual Setup Required)**

**IMPORTANT:** Luffy **does NOT automatically checkout branches**. The repository at `git_repo_path` must already be on the correct branch.

**Why?**
- Avoids conflicts with local changes
- Prevents accidental overwrites
- Gives administrators full control
- Supports multiple deployment strategies

**Setup Options:**

#### **Option A: Manual Branch Setup (Recommended for Production)**

```bash
# Clone repository
git clone https://github.com/org/web-app /repos/web-app

# Checkout desired branch
cd /repos/web-app
git checkout main

# Keep it updated (run periodically)
git pull origin main
```

#### **Option B: Automated Git Pull (via Cron/Script)**

Create a script to keep repositories updated:

```bash
#!/bin/bash
# /scripts/update_repos.sh

# Update web-app repository
cd /repos/web-app
git fetch origin
git checkout main
git pull origin main

# Update api-service repository
cd /repos/api-service
git fetch origin
git checkout develop
git pull origin develop
```

**Cron Job:**
```bash
# Update repositories every hour
0 * * * * /scripts/update_repos.sh >> /var/log/repo_updates.log 2>&1
```

#### **Option C: Webhook-Triggered Updates**

Set up a webhook endpoint that pulls latest code when pushes occur:

```python
@app.post("/webhooks/git-push")
async def handle_git_push(payload: dict):
    service_id = payload.get('service_id')
    branch = payload.get('branch')
    
    # Update repository
    repo_path = get_service_repo_path(service_id)
    subprocess.run(['git', 'pull', 'origin', branch], cwd=repo_path)
    
    # Trigger code indexing
    index_code_repository.delay(service_id=service_id, trigger_reason='webhook')
```

#### **Option D: Docker Volume Mounts (for Containerized Deployments)**

Mount repositories as volumes in docker-compose.yml:

```yaml
services:
  luffy-api:
    volumes:
      - /host/repos/web-app:/repos/web-app:ro  # Read-only mount
      - /host/repos/api-service:/repos/api-service:ro
```

**Host manages repositories:**
```bash
# On host machine
cd /host/repos/web-app
git pull origin main

cd /host/repos/api-service
git pull origin develop
```

---

### 5. **Commit SHA Tracking**

Luffy tracks which commit was last indexed to enable **incremental indexing**:

```python
# Check if code changed since last index
def _should_index_code_for_service(service_id: str) -> bool:
    service = db.query(Service).filter(Service.id == service_id).first()
    
    # Get current commit SHA
    current_commit = _get_current_commit_sha(service.git_repo_path)
    
    # Compare with last indexed commit
    if current_commit == service.last_indexed_commit:
        logger.info(f"Code unchanged for {service_id}")
        return False  # Skip indexing
    
    logger.info(f"Code changed: {service.last_indexed_commit} → {current_commit}")
    return True  # Trigger indexing
```

**Benefits:**
- Only indexes when code actually changes
- Saves resources (no redundant indexing)
- Tracks exact version indexed
- Enables incremental indexing (only changed files)

---

### 6. **Incremental vs Full Indexing**

#### **Incremental Indexing (Default)**

Only indexes files that changed since last commit:

```python
def index_repository(self, languages: List[str], force_full: bool = False):
    last_commit = self._get_last_indexed_commit()
    
    if not force_full and last_commit and last_commit != self.commit_sha:
        # Incremental mode: only changed files
        files_to_index = self._get_changed_files_since_commit(last_commit, languages)
        stats['mode'] = 'incremental'
    else:
        # Full mode: all files
        files_to_index = self._get_all_files(languages)
        stats['mode'] = 'full'
```

**Changed Files Detection:**
```python
def _get_changed_files_since_commit(self, last_commit: str, languages: List[str]):
    # Get diff between commits
    diff = self.repo.commit(last_commit).diff(self.repo.head.commit)
    
    # Filter by language extensions
    changed_files = []
    for item in diff:
        if item.a_path.endswith(('.py', '.java')):
            file_path = self.repo_path / item.a_path
            if file_path.exists():
                changed_files.append(file_path)
    
    return changed_files
```

#### **Full Indexing (Manual Trigger)**

Indexes all files regardless of changes:

```bash
# Via API
curl -X POST "http://localhost:8000/api/v1/code-indexing/services/web-app/trigger?force_full=true"

# Via UI
Settings → Code Indexing Control → ✓ Force full re-indexing → Trigger Indexing
```

---

## 🎯 Complete Workflow

### **Scenario: New Service with Git Repository**

**1. Clone Repository Locally:**
```bash
git clone https://github.com/org/web-app /repos/web-app
cd /repos/web-app
git checkout main
```

**2. Create Service in Luffy:**
```bash
curl -X POST "http://localhost:8000/api/v1/services" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "web-app",
    "name": "Web Application",
    "git_repo_path": "/repos/web-app",
    "git_branch": "main",
    "repository_url": "https://github.com/org/web-app",
    "code_indexing_enabled": true
  }'
```

**3. Trigger Initial Indexing:**
```bash
curl -X POST "http://localhost:8000/api/v1/code-indexing/services/web-app/trigger?force_full=true"
```

**4. Automatic On-Demand Indexing:**
- When exceptions are detected, Luffy automatically checks if code changed
- If changed, triggers incremental indexing
- Only indexes modified files

**5. Keep Repository Updated:**
```bash
# Option A: Manual updates
cd /repos/web-app && git pull origin main

# Option B: Automated cron job
0 * * * * cd /repos/web-app && git pull origin main

# Option C: Webhook on Git push
# (Luffy receives webhook, pulls latest, triggers indexing)
```

---

## 🔧 Multi-Branch Support

### **Scenario: Different Branches for Different Environments**

**Production Service (main branch):**
```json
{
  "service_id": "web-app-prod",
  "git_repo_path": "/repos/web-app-prod",
  "git_branch": "main",
  "code_indexing_enabled": true
}
```

**Staging Service (develop branch):**
```json
{
  "service_id": "web-app-staging",
  "git_repo_path": "/repos/web-app-staging",
  "git_branch": "develop",
  "code_indexing_enabled": true
}
```

**Setup:**
```bash
# Production repository
git clone https://github.com/org/web-app /repos/web-app-prod
cd /repos/web-app-prod
git checkout main

# Staging repository
git clone https://github.com/org/web-app /repos/web-app-staging
cd /repos/web-app-staging
git checkout develop
```

**Result:**
- Production exceptions analyzed against `main` branch code
- Staging exceptions analyzed against `develop` branch code
- Each environment has correct code context

---

## 📊 Status Tracking

### **Check Indexing Status:**

```bash
curl "http://localhost:8000/api/v1/code-indexing/services/web-app/status"
```

**Response:**
```json
{
  "service_id": "web-app",
  "service_name": "Web Application",
  "status": "completed",
  "last_indexed_at": "2025-12-07T14:30:00Z",
  "last_indexed_commit": "abc123def456",
  "indexing_trigger": "exception_detected",
  "git_repo_path": "/repos/web-app",
  "git_branch": "main",
  "code_indexing_enabled": true
}
```

### **View Indexing History:**

```bash
curl "http://localhost:8000/api/v1/code-indexing/services/web-app/history"
```

**Response:**
```json
{
  "service_id": "web-app",
  "history": [
    {
      "repository": "web-app",
      "last_indexed_commit": "abc123def456",
      "last_indexed_at": "2025-12-07T14:30:00Z",
      "total_files_indexed": 45,
      "total_blocks_indexed": 234,
      "indexing_mode": "incremental"
    },
    {
      "repository": "web-app",
      "last_indexed_commit": "def456abc123",
      "last_indexed_at": "2025-12-07T10:15:00Z",
      "total_files_indexed": 120,
      "total_blocks_indexed": 678,
      "indexing_mode": "full"
    }
  ]
}
```

---

## 🐛 Troubleshooting

### **Issue: "No Git repository configured"**

**Cause:** `git_repo_path` not set or invalid

**Solution:**
```bash
# Update service configuration
curl -X PUT "http://localhost:8000/api/v1/services/web-app/config" \
  -H "Content-Type: application/json" \
  -d '{
    "git_repo_path": "/repos/web-app",
    "git_branch": "main"
  }'
```

### **Issue: "Code unchanged, skipping indexing"**

**Cause:** Repository not updated with latest code

**Solution:**
```bash
# Pull latest code
cd /repos/web-app
git pull origin main

# Verify commit changed
git log -1 --oneline

# Trigger indexing
curl -X POST "http://localhost:8000/api/v1/code-indexing/services/web-app/trigger"
```

### **Issue: "Wrong branch being indexed"**

**Cause:** Repository on different branch than configured

**Solution:**
```bash
# Check current branch
cd /repos/web-app
git branch

# Checkout correct branch
git checkout main

# Update service config if needed
curl -X PUT "http://localhost:8000/api/v1/services/web-app/config" \
  -d '{"git_branch": "main"}'
```

### **Issue: "Indexing fails with Git errors"**

**Cause:** Repository in detached HEAD state or has conflicts

**Solution:**
```bash
cd /repos/web-app

# Check status
git status

# Reset to clean state
git fetch origin
git reset --hard origin/main

# Trigger indexing again
curl -X POST "http://localhost:8000/api/v1/code-indexing/services/web-app/trigger"
```

---

## 🔒 Security Considerations

### **1. Repository Access**

- Use **read-only** access for Luffy
- Don't give write permissions
- Use SSH keys or deploy tokens

### **2. File Permissions**

```bash
# Set appropriate permissions
chmod 755 /repos
chmod -R 644 /repos/web-app
```

### **3. Docker Volume Mounts**

```yaml
volumes:
  - /host/repos/web-app:/repos/web-app:ro  # Read-only!
```

---

## 📚 Best Practices

### **1. Repository Organization**

```
/repos/
├── web-app-prod/     (main branch)
├── web-app-staging/  (develop branch)
├── api-service/      (main branch)
└── mobile-backend/   (release/v2.0 branch)
```

### **2. Update Strategy**

**For Production:**
- Manual updates before indexing
- Controlled deployment process
- Verify commit SHA before indexing

**For Development:**
- Automated updates (cron/webhook)
- Frequent indexing
- Fast feedback loop

### **3. Branch Naming Convention**

- Production: `main` or `master`
- Staging: `develop` or `staging`
- Features: `feature/feature-name`
- Releases: `release/v1.0.0`

---

## 🎉 Summary

**How Repository Syncing Works:**

1. ✅ **Service Configuration**: Each service has `git_repo_path` and `git_branch`
2. ✅ **Repository Access**: CodeIndexer opens Git repo using GitPython
3. ✅ **Commit Tracking**: Tracks current HEAD commit SHA
4. ✅ **Change Detection**: Compares current commit with last indexed commit
5. ✅ **Incremental Indexing**: Only indexes changed files
6. ✅ **Manual Updates**: Administrator keeps repositories updated
7. ✅ **Flexible Strategies**: Supports manual, cron, webhook, or volume mount updates

**Key Points:**
- 🔴 **Luffy does NOT automatically checkout branches**
- 🟢 **Repository must be on correct branch before indexing**
- 🟢 **Commit SHA tracking enables smart incremental indexing**
- 🟢 **Multiple strategies for keeping repos updated**
- 🟢 **Each service can have different repository and branch**

**Result: Flexible, efficient code indexing that respects your Git workflow!** 🚀

---

**Last Updated:** 2025-12-07  
**Version:** 1.0.0
