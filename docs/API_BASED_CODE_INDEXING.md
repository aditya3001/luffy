# API-Based Code Indexing (GitHub/GitLab)

## 📋 Overview

This document explains how to index code repositories directly from GitHub/GitLab APIs **without storing code locally**. This approach uses access tokens to fetch code on-demand, eliminating the need for local repository clones.

---

## 🎯 Benefits of API-Based Indexing

### **Advantages:**
- ✅ **No Local Storage**: No need to clone/store repositories
- ✅ **Always Fresh**: Fetches latest code directly from source
- ✅ **Multi-Branch Support**: Easy switching between branches
- ✅ **Scalable**: Works with hundreds of repositories
- ✅ **Secure**: Uses access tokens with fine-grained permissions
- ✅ **Cloud-Native**: Perfect for containerized deployments
- ✅ **No Git Dependencies**: No need for Git CLI or GitPython

### **Comparison:**

| Feature | Local Clone | API-Based |
|---------|-------------|-----------|
| Storage Required | High (full repos) | Minimal (cache only) |
| Setup Complexity | Medium (clone, update) | Low (just token) |
| Freshness | Manual updates | Always latest |
| Scalability | Limited by disk | Unlimited |
| Multi-Branch | Complex | Simple |
| Security | File permissions | Token-based |

---

## 🔑 Access Token Setup

### **GitHub Personal Access Token (Classic)**

**1. Create Token:**
- Go to: https://github.com/settings/tokens
- Click: "Generate new token" → "Generate new token (classic)"
- Name: `Luffy Code Indexing`
- Expiration: Choose appropriate duration
- Scopes: Select `repo` (for private repos) or `public_repo` (for public only)
- Click: "Generate token"
- **Copy token immediately** (shown only once)

**2. Token Permissions:**
```
✓ repo (Full control of private repositories)
  ✓ repo:status
  ✓ repo_deployment
  ✓ public_repo
  ✓ repo:invite
  ✓ security_events
```

**Or for public repos only:**
```
✓ public_repo (Access public repositories)
```

**3. Store Token Securely:**
```bash
# In .env file
GITHUB_ACCESS_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GITHUB_ORG=your-organization
```

---

### **GitHub Fine-Grained Personal Access Token (Recommended)**

**1. Create Token:**
- Go to: https://github.com/settings/tokens?type=beta
- Click: "Generate new token"
- Name: `Luffy Code Indexing`
- Expiration: Choose duration
- Repository access: Select specific repositories
- Permissions:
  - **Contents**: Read-only
  - **Metadata**: Read-only
  - **Commit statuses**: Read-only (optional)

**2. Advantages:**
- More secure (repository-specific)
- Granular permissions
- Better audit trail
- Automatic expiration

---

### **GitLab Personal Access Token**

**1. Create Token:**
- Go to: https://gitlab.com/-/profile/personal_access_tokens
- Name: `Luffy Code Indexing`
- Expiration: Choose duration
- Scopes: Select `read_api` and `read_repository`
- Click: "Create personal access token"
- **Copy token immediately**

**2. Token Scopes:**
```
✓ read_api (Read-only API access)
✓ read_repository (Read-only repository access)
```

**3. Store Token:**
```bash
# In .env file
GITLAB_ACCESS_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx
GITLAB_GROUP=your-group
```

---

## 🏗️ Implementation Architecture

### **High-Level Flow:**

```
1. User configures service with GitHub/GitLab URL + token
   ↓
2. Indexing triggered (manual or automatic)
   ↓
3. Fetch repository tree via API (list all files)
   ↓
4. Download code files via API (only .py, .java files)
   ↓
5. Parse code in-memory (no disk storage)
   ↓
6. Extract functions/classes
   ↓
7. Generate embeddings
   ↓
8. Store in vector database
   ↓
9. Track commit SHA for incremental indexing
```

---

## 📝 Service Configuration

### **GitHub Repository:**

```json
{
  "service_id": "web-app",
  "name": "Web Application",
  "repository_url": "https://github.com/org/web-app",
  "git_branch": "main",
  "git_provider": "github",
  "access_token": "ghp_xxxxxxxxxxxx",
  "code_indexing_enabled": true
}
```

### **GitLab Repository:**

```json
{
  "service_id": "api-service",
  "name": "API Service",
  "repository_url": "https://gitlab.com/group/api-service",
  "git_branch": "develop",
  "git_provider": "gitlab",
  "access_token": "glpat-xxxxxxxxxxxx",
  "code_indexing_enabled": true
}
```

---

## 🔧 API Implementation

### **1. GitHub API - Fetch Repository Tree**

**Endpoint:**
```
GET https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1
```

**Request:**
```python
import requests

def fetch_github_tree(owner, repo, branch, token):
    """Fetch repository file tree from GitHub API"""
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    params = {"recursive": "1"}
    
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    
    return response.json()
```

**Response:**
```json
{
  "sha": "abc123def456",
  "tree": [
    {
      "path": "src/main.py",
      "type": "blob",
      "sha": "file123",
      "size": 1234,
      "url": "https://api.github.com/repos/org/repo/git/blobs/file123"
    },
    {
      "path": "src/utils/helper.py",
      "type": "blob",
      "sha": "file456",
      "size": 567
    }
  ]
}
```

**Filter Python/Java Files:**
```python
def filter_code_files(tree):
    """Filter only Python and Java files"""
    code_files = []
    for item in tree['tree']:
        if item['type'] == 'blob':
            if item['path'].endswith(('.py', '.java')):
                code_files.append(item)
    return code_files
```

---

### **2. GitHub API - Fetch File Content**

**Endpoint:**
```
GET https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}
```

**Request:**
```python
import base64

def fetch_github_file(owner, repo, path, branch, token):
    """Fetch file content from GitHub API"""
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }
    params = {"ref": branch}
    
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    
    data = response.json()
    
    # Decode base64 content
    content = base64.b64decode(data['content']).decode('utf-8')
    
    return {
        'path': path,
        'content': content,
        'sha': data['sha'],
        'size': data['size']
    }
```

**Response:**
```json
{
  "name": "main.py",
  "path": "src/main.py",
  "sha": "file123",
  "size": 1234,
  "content": "ZGVmIG1haW4oKToKICAgIHBhc3M=",  // base64 encoded
  "encoding": "base64"
}
```

---

### **3. GitLab API - Fetch Repository Tree**

**Endpoint:**
```
GET https://gitlab.com/api/v4/projects/{project_id}/repository/tree?recursive=true&ref={branch}
```

**Request:**
```python
def fetch_gitlab_tree(project_id, branch, token):
    """Fetch repository file tree from GitLab API"""
    url = f"https://gitlab.com/api/v4/projects/{project_id}/repository/tree"
    headers = {
        "PRIVATE-TOKEN": token
    }
    params = {
        "recursive": "true",
        "ref": branch,
        "per_page": 100
    }
    
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    
    return response.json()
```

**Response:**
```json
[
  {
    "id": "abc123",
    "name": "main.py",
    "type": "blob",
    "path": "src/main.py",
    "mode": "100644"
  },
  {
    "id": "def456",
    "name": "helper.py",
    "type": "blob",
    "path": "src/utils/helper.py",
    "mode": "100644"
  }
]
```

---

### **4. GitLab API - Fetch File Content**

**Endpoint:**
```
GET https://gitlab.com/api/v4/projects/{project_id}/repository/files/{file_path}/raw?ref={branch}
```

**Request:**
```python
import urllib.parse

def fetch_gitlab_file(project_id, path, branch, token):
    """Fetch file content from GitLab API"""
    # URL encode the file path
    encoded_path = urllib.parse.quote(path, safe='')
    
    url = f"https://gitlab.com/api/v4/projects/{project_id}/repository/files/{encoded_path}/raw"
    headers = {
        "PRIVATE-TOKEN": token
    }
    params = {"ref": branch}
    
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    
    return {
        'path': path,
        'content': response.text,
        'size': len(response.text)
    }
```

---

## 🚀 Complete Indexing Workflow

### **Step-by-Step Process:**

```python
def index_repository_from_api(service_id: str, force_full: bool = False):
    """
    Index repository using GitHub/GitLab API without local storage.
    
    Args:
        service_id: Service ID to index
        force_full: Force full indexing (default: incremental)
    """
    
    # 1. Get service configuration
    service = get_service(service_id)
    
    # 2. Parse repository URL
    owner, repo = parse_repo_url(service.repository_url)
    
    # 3. Fetch current commit SHA
    current_commit = fetch_latest_commit_sha(
        owner, repo, service.git_branch, service.access_token
    )
    
    # 4. Check if indexing needed (incremental)
    if not force_full and current_commit == service.last_indexed_commit:
        logger.info(f"Code unchanged for {service_id}, skipping indexing")
        return {"status": "skipped", "reason": "no changes"}
    
    # 5. Fetch repository tree
    tree = fetch_repository_tree(
        owner, repo, service.git_branch, service.access_token, service.git_provider
    )
    
    # 6. Filter code files (.py, .java)
    code_files = filter_code_files(tree, languages=['python', 'java'])
    
    # 7. Fetch and index each file
    stats = {'total_files': 0, 'total_blocks': 0, 'errors': 0}
    
    for file_info in code_files:
        try:
            # Fetch file content via API
            file_data = fetch_file_content(
                owner, repo, file_info['path'], 
                service.git_branch, service.access_token, service.git_provider
            )
            
            # Parse code in-memory (no disk write)
            blocks = parse_code_file(
                file_data['path'], 
                file_data['content'],
                language='python' if file_data['path'].endswith('.py') else 'java'
            )
            
            # Store in vector database
            for block in blocks:
                store_code_block(block, service_id, current_commit)
            
            stats['total_files'] += 1
            stats['total_blocks'] += len(blocks)
            
        except Exception as e:
            logger.error(f"Error indexing {file_info['path']}: {e}")
            stats['errors'] += 1
    
    # 8. Update service metadata
    update_service_indexing_status(
        service_id, 
        last_indexed_commit=current_commit,
        last_indexed_at=datetime.utcnow()
    )
    
    return {
        'status': 'success',
        'commit_sha': current_commit,
        'files_indexed': stats['total_files'],
        'blocks_indexed': stats['total_blocks'],
        'errors': stats['errors']
    }
```

---

## 📦 Helper Functions

### **Parse Repository URL:**

```python
def parse_repo_url(url: str) -> tuple:
    """
    Parse GitHub/GitLab URL to extract owner and repo.
    
    Examples:
        https://github.com/org/repo → ('org', 'repo')
        https://gitlab.com/group/project → ('group', 'project')
    """
    # Remove .git suffix if present
    url = url.rstrip('.git')
    
    # Parse URL
    parts = url.rstrip('/').split('/')
    
    if 'github.com' in url or 'gitlab.com' in url:
        owner = parts[-2]
        repo = parts[-1]
        return owner, repo
    
    raise ValueError(f"Unsupported repository URL: {url}")
```

### **Fetch Latest Commit SHA:**

**GitHub:**
```python
def fetch_github_commit_sha(owner: str, repo: str, branch: str, token: str) -> str:
    """Fetch latest commit SHA for a branch"""
    url = f"https://api.github.com/repos/{owner}/{repo}/commits/{branch}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    return response.json()['sha']
```

**GitLab:**
```python
def fetch_gitlab_commit_sha(project_id: str, branch: str, token: str) -> str:
    """Fetch latest commit SHA for a branch"""
    url = f"https://gitlab.com/api/v4/projects/{project_id}/repository/commits/{branch}"
    headers = {"PRIVATE-TOKEN": token}
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    return response.json()['id']
```

### **Get GitLab Project ID:**

```python
def get_gitlab_project_id(owner: str, repo: str, token: str) -> str:
    """Get GitLab project ID from owner/repo"""
    # URL encode the project path
    project_path = f"{owner}/{repo}"
    encoded_path = urllib.parse.quote(project_path, safe='')
    
    url = f"https://gitlab.com/api/v4/projects/{encoded_path}"
    headers = {"PRIVATE-TOKEN": token}
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    return str(response.json()['id'])
```

---

## 🔄 Incremental Indexing

### **Strategy:**

**1. Track Commit SHA:**
```python
# Store last indexed commit
service.last_indexed_commit = "abc123def456"
service.last_indexed_at = datetime.utcnow()
```

**2. Compare on Next Run:**
```python
current_commit = fetch_latest_commit_sha(...)

if current_commit == service.last_indexed_commit:
    # No changes, skip indexing
    return {"status": "skipped"}
else:
    # Code changed, index all files
    index_all_files(...)
```

**3. Optional: Fetch Changed Files Only (Advanced):**

**GitHub Compare API:**
```python
def fetch_changed_files(owner, repo, base_commit, head_commit, token):
    """Fetch files changed between two commits"""
    url = f"https://api.github.com/repos/{owner}/{repo}/compare/{base_commit}...{head_commit}"
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    changed_files = []
    for file in response.json()['files']:
        if file['filename'].endswith(('.py', '.java')):
            changed_files.append(file['filename'])
    
    return changed_files
```

**GitLab Compare API:**
```python
def fetch_gitlab_changed_files(project_id, base_commit, head_commit, token):
    """Fetch files changed between two commits"""
    url = f"https://gitlab.com/api/v4/projects/{project_id}/repository/compare"
    headers = {"PRIVATE-TOKEN": token}
    params = {"from": base_commit, "to": head_commit}
    
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    
    changed_files = []
    for diff in response.json()['diffs']:
        if diff['new_path'].endswith(('.py', '.java')):
            changed_files.append(diff['new_path'])
    
    return changed_files
```

---

## 🔒 Security Best Practices

### **1. Token Storage:**

**Environment Variables (Recommended):**
```bash
# .env file
GITHUB_ACCESS_TOKEN=ghp_xxxxxxxxxxxx
GITLAB_ACCESS_TOKEN=glpat-xxxxxxxxxxxx
```

**Database Encryption:**
```python
from cryptography.fernet import Fernet

# Encrypt token before storing
def encrypt_token(token: str, encryption_key: str) -> str:
    f = Fernet(encryption_key)
    return f.encrypt(token.encode()).decode()

# Decrypt when using
def decrypt_token(encrypted_token: str, encryption_key: str) -> str:
    f = Fernet(encryption_key)
    return f.decrypt(encrypted_token.encode()).decode()
```

**AWS Secrets Manager:**
```python
import boto3

def get_github_token(service_id: str) -> str:
    """Fetch token from AWS Secrets Manager"""
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(
        SecretId=f"luffy/github-token/{service_id}"
    )
    return response['SecretString']
```

### **2. Token Permissions:**

**Principle of Least Privilege:**
- ✅ Use read-only tokens
- ✅ Limit to specific repositories (fine-grained tokens)
- ✅ Set expiration dates
- ✅ Rotate tokens regularly
- ❌ Never use tokens with write access
- ❌ Never commit tokens to Git

### **3. Rate Limiting:**

**GitHub Rate Limits:**
- Authenticated: 5,000 requests/hour
- Unauthenticated: 60 requests/hour

**Handle Rate Limits:**
```python
def fetch_with_retry(url, headers, max_retries=3):
    """Fetch with rate limit handling"""
    for attempt in range(max_retries):
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            return response.json()
        
        elif response.status_code == 403:
            # Rate limit exceeded
            reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
            wait_seconds = reset_time - time.time()
            
            if wait_seconds > 0:
                logger.warning(f"Rate limit exceeded, waiting {wait_seconds}s")
                time.sleep(wait_seconds + 1)
                continue
        
        elif response.status_code == 401:
            raise Exception("Invalid access token")
        
        else:
            response.raise_for_status()
    
    raise Exception("Max retries exceeded")
```

### **4. Input Validation:**

```python
def validate_repository_url(url: str) -> bool:
    """Validate repository URL"""
    allowed_domains = ['github.com', 'gitlab.com']
    
    for domain in allowed_domains:
        if domain in url:
            return True
    
    raise ValueError(f"Unsupported repository URL: {url}")

def validate_branch_name(branch: str) -> bool:
    """Validate branch name"""
    # Prevent path traversal
    if '..' in branch or '/' in branch:
        raise ValueError(f"Invalid branch name: {branch}")
    
    return True
```

---

## 📊 Performance Optimization

### **1. Parallel File Fetching:**

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_files_parallel(files, owner, repo, branch, token, max_workers=10):
    """Fetch multiple files in parallel"""
    results = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all fetch tasks
        future_to_file = {
            executor.submit(fetch_github_file, owner, repo, f['path'], branch, token): f
            for f in files
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_file):
            file_info = future_to_file[future]
            try:
                file_data = future.result()
                results.append(file_data)
            except Exception as e:
                logger.error(f"Error fetching {file_info['path']}: {e}")
    
    return results
```

### **2. Caching:**

```python
from functools import lru_cache
import hashlib

@lru_cache(maxsize=1000)
def fetch_file_cached(owner, repo, path, commit_sha, token):
    """Cache file content by commit SHA"""
    # File content won't change for a specific commit
    return fetch_github_file(owner, repo, path, commit_sha, token)
```

### **3. Batch Processing:**

```python
def index_in_batches(files, batch_size=50):
    """Process files in batches to avoid memory issues"""
    for i in range(0, len(files), batch_size):
        batch = files[i:i + batch_size]
        
        # Fetch batch
        file_contents = fetch_files_parallel(batch, ...)
        
        # Index batch
        for file_data in file_contents:
            index_file(file_data)
        
        # Clear memory
        del file_contents
```

---

## 🎯 Service Configuration UI

### **Frontend Form:**

```typescript
interface ServiceConfig {
  id: string;
  name: string;
  repository_url: string;
  git_branch: string;
  git_provider: 'github' | 'gitlab';
  access_token: string;
  code_indexing_enabled: boolean;
}

const ServiceForm = () => {
  return (
    <Form>
      <Form.Item label="Repository URL" name="repository_url" required>
        <Input placeholder="https://github.com/org/repo" />
      </Form.Item>
      
      <Form.Item label="Branch" name="git_branch" required>
        <Input placeholder="main" />
      </Form.Item>
      
      <Form.Item label="Git Provider" name="git_provider" required>
        <Select>
          <Option value="github">GitHub</Option>
          <Option value="gitlab">GitLab</Option>
        </Select>
      </Form.Item>
      
      <Form.Item label="Access Token" name="access_token" required>
        <Input.Password placeholder="ghp_xxxxxxxxxxxx" />
      </Form.Item>
      
      <Form.Item label="Enable Code Indexing" name="code_indexing_enabled">
        <Switch />
      </Form.Item>
    </Form>
  );
};
```

---

## 🧪 Testing

### **Test GitHub Connection:**

```python
def test_github_connection(owner: str, repo: str, token: str) -> dict:
    """Test GitHub API connection and token validity"""
    try:
        # Test repository access
        url = f"https://api.github.com/repos/{owner}/{repo}"
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        repo_data = response.json()
        
        return {
            "status": "success",
            "repository": repo_data['full_name'],
            "default_branch": repo_data['default_branch'],
            "private": repo_data['private'],
            "size_kb": repo_data['size']
        }
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            return {"status": "error", "message": "Invalid access token"}
        elif e.response.status_code == 404:
            return {"status": "error", "message": "Repository not found"}
        else:
            return {"status": "error", "message": str(e)}
```

### **Test GitLab Connection:**

```python
def test_gitlab_connection(project_path: str, token: str) -> dict:
    """Test GitLab API connection and token validity"""
    try:
        encoded_path = urllib.parse.quote(project_path, safe='')
        url = f"https://gitlab.com/api/v4/projects/{encoded_path}"
        headers = {"PRIVATE-TOKEN": token}
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        project_data = response.json()
        
        return {
            "status": "success",
            "project": project_data['path_with_namespace'],
            "default_branch": project_data['default_branch'],
            "visibility": project_data['visibility']
        }
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            return {"status": "error", "message": "Invalid access token"}
        elif e.response.status_code == 404:
            return {"status": "error", "message": "Project not found"}
        else:
            return {"status": "error", "message": str(e)}
```

---

## 📋 API Endpoint Examples

### **Create Service with GitHub:**

```bash
curl -X POST "http://localhost:8000/api/v1/services" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "web-app",
    "name": "Web Application",
    "repository_url": "https://github.com/org/web-app",
    "git_branch": "main",
    "git_provider": "github",
    "access_token": "ghp_xxxxxxxxxxxx",
    "code_indexing_enabled": true
  }'
```

### **Test Connection:**

```bash
curl -X POST "http://localhost:8000/api/v1/services/web-app/test-connection"
```

**Response:**
```json
{
  "status": "success",
  "repository": "org/web-app",
  "default_branch": "main",
  "private": true,
  "size_kb": 12345
}
```

### **Trigger Indexing:**

```bash
curl -X POST "http://localhost:8000/api/v1/code-indexing/services/web-app/trigger?force_full=true"
```

**Response:**
```json
{
  "message": "Code indexing triggered successfully",
  "service_id": "web-app",
  "task_id": "abc-123-def-456",
  "commit_sha": "abc123def456",
  "files_to_index": 45
}
```

---

## 🐛 Troubleshooting

### **Issue: "Invalid access token"**

**Cause:** Token expired or invalid

**Solution:**
```bash
# Generate new token
# Update service configuration
curl -X PUT "http://localhost:8000/api/v1/services/web-app/config" \
  -d '{"access_token": "new_token_here"}'
```

### **Issue: "Rate limit exceeded"**

**Cause:** Too many API requests

**Solution:**
- Wait for rate limit reset (check `X-RateLimit-Reset` header)
- Use caching to reduce requests
- Implement exponential backoff
- Consider GitHub Apps for higher limits (15,000 req/hour)

### **Issue: "Repository not found"**

**Cause:** Wrong URL or insufficient permissions

**Solution:**
- Verify repository URL is correct
- Ensure token has access to repository
- For private repos, ensure `repo` scope is enabled

### **Issue: "File too large"**

**Cause:** GitHub/GitLab API limits file size

**Solution:**
```python
# Skip large files
MAX_FILE_SIZE = 1_000_000  # 1MB

def should_index_file(file_info):
    if file_info['size'] > MAX_FILE_SIZE:
        logger.warning(f"Skipping large file: {file_info['path']}")
        return False
    return True
```

---

## 🎉 Summary

### **API-Based Indexing Workflow:**

1. ✅ **Configure Service**: Add repository URL + access token
2. ✅ **Test Connection**: Verify token and repository access
3. ✅ **Fetch Tree**: Get list of all files via API
4. ✅ **Filter Files**: Select only .py and .java files
5. ✅ **Fetch Content**: Download file content via API
6. ✅ **Parse In-Memory**: Extract functions/classes without disk storage
7. ✅ **Store Embeddings**: Save to vector database
8. ✅ **Track Commit**: Store SHA for incremental indexing

### **Key Advantages:**

- 🚀 **No Local Storage**: Eliminates disk space requirements
- 🔄 **Always Fresh**: Fetches latest code on-demand
- 🔒 **Secure**: Token-based authentication with fine-grained permissions
- 📈 **Scalable**: Works with unlimited repositories
- ☁️ **Cloud-Native**: Perfect for containerized deployments

### **Supported Platforms:**

- ✅ GitHub (github.com)
- ✅ GitHub Enterprise
- ✅ GitLab (gitlab.com)
- ✅ GitLab Self-Hosted
- 🔜 Bitbucket (coming soon)
- 🔜 Azure DevOps (coming soon)

---

## 📚 Next Steps

1. **Implement API Client**: Create GitHub/GitLab API wrapper
2. **Update Service Model**: Add `git_provider` and `access_token` fields
3. **Modify CodeIndexer**: Replace local file access with API calls
4. **Add Connection Testing**: Implement test endpoints
5. **Update UI**: Add token input fields
6. **Add Documentation**: Update user guides

---

**Last Updated:** 2025-12-07  
**Version:** 1.0.0  
**Status:** Ready for Implementation 🚀
