# API-Based Code Indexing - Implementation Checklist

## 📋 Overview

This checklist guides you through implementing API-based code indexing for GitHub/GitLab repositories without local storage.

---

## ✅ Phase 1: Database Schema Updates

### **1.1 Update Service Model**

**File:** `src/storage/models.py`

```python
class Service(Base):
    # Existing fields...
    
    # NEW: Git provider and authentication
    git_provider = Column(String(50))  # 'github', 'gitlab', 'bitbucket'
    access_token_encrypted = Column(Text)  # Encrypted access token
    
    # MODIFY: Make these optional (not all services need local repos)
    git_repo_path = Column(String(500), nullable=True)  # Now optional
    
    # NEW: Repository metadata
    repository_owner = Column(String(255))  # e.g., 'org' from 'org/repo'
    repository_name = Column(String(255))   # e.g., 'repo' from 'org/repo'
    repository_id = Column(String(255))     # GitLab project ID
```

### **1.2 Create Migration Script**

**File:** `scripts/migrate_api_based_indexing.py`

```python
"""
Add git_provider and access_token fields to services table
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('services', sa.Column('git_provider', sa.String(50)))
    op.add_column('services', sa.Column('access_token_encrypted', sa.Text()))
    op.add_column('services', sa.Column('repository_owner', sa.String(255)))
    op.add_column('services', sa.Column('repository_name', sa.String(255)))
    op.add_column('services', sa.Column('repository_id', sa.String(255)))
    
    # Make git_repo_path nullable
    op.alter_column('services', 'git_repo_path', nullable=True)

def downgrade():
    op.drop_column('services', 'git_provider')
    op.drop_column('services', 'access_token_encrypted')
    op.drop_column('services', 'repository_owner')
    op.drop_column('services', 'repository_name')
    op.drop_column('services', 'repository_id')
```

**Run Migration:**
```bash
python scripts/migrate_api_based_indexing.py
```

---

## ✅ Phase 2: Git API Client Implementation

### **2.1 Create GitHub API Client**

**File:** `src/integrations/github_client.py`

```python
"""
GitHub API client for fetching repository code
"""
import requests
import base64
from typing import List, Dict, Any

class GitHubClient:
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
    
    def get_repository_tree(self, owner: str, repo: str, branch: str) -> Dict:
        """Fetch repository file tree"""
        # Implementation from API_BASED_CODE_INDEXING.md
        pass
    
    def get_file_content(self, owner: str, repo: str, path: str, branch: str) -> Dict:
        """Fetch file content"""
        # Implementation from API_BASED_CODE_INDEXING.md
        pass
    
    def get_latest_commit(self, owner: str, repo: str, branch: str) -> str:
        """Get latest commit SHA"""
        # Implementation from API_BASED_CODE_INDEXING.md
        pass
    
    def test_connection(self, owner: str, repo: str) -> Dict:
        """Test repository access"""
        # Implementation from API_BASED_CODE_INDEXING.md
        pass
```

### **2.2 Create GitLab API Client**

**File:** `src/integrations/gitlab_client.py`

```python
"""
GitLab API client for fetching repository code
"""
import requests
import urllib.parse
from typing import List, Dict, Any

class GitLabClient:
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://gitlab.com/api/v4"
        self.headers = {
            "PRIVATE-TOKEN": token
        }
    
    def get_repository_tree(self, project_id: str, branch: str) -> List[Dict]:
        """Fetch repository file tree"""
        # Implementation from API_BASED_CODE_INDEXING.md
        pass
    
    def get_file_content(self, project_id: str, path: str, branch: str) -> Dict:
        """Fetch file content"""
        # Implementation from API_BASED_CODE_INDEXING.md
        pass
    
    def get_latest_commit(self, project_id: str, branch: str) -> str:
        """Get latest commit SHA"""
        # Implementation from API_BASED_CODE_INDEXING.md
        pass
    
    def get_project_id(self, owner: str, repo: str) -> str:
        """Get GitLab project ID from owner/repo"""
        # Implementation from API_BASED_CODE_INDEXING.md
        pass
    
    def test_connection(self, project_path: str) -> Dict:
        """Test project access"""
        # Implementation from API_BASED_CODE_INDEXING.md
        pass
```

### **2.3 Create Git Client Factory**

**File:** `src/integrations/git_client_factory.py`

```python
"""
Factory for creating Git API clients
"""
from src.integrations.github_client import GitHubClient
from src.integrations.gitlab_client import GitLabClient

class GitClientFactory:
    @staticmethod
    def create(provider: str, token: str):
        """Create appropriate Git client based on provider"""
        if provider == 'github':
            return GitHubClient(token)
        elif provider == 'gitlab':
            return GitLabClient(token)
        else:
            raise ValueError(f"Unsupported Git provider: {provider}")
```

---

## ✅ Phase 3: Update Code Indexer

### **3.1 Modify CodeIndexer Class**

**File:** `src/services/code_indexer.py`

```python
class CodeIndexer:
    def __init__(
        self, 
        repo_path: str = None,  # Optional now
        version: str = None,
        git_client = None,      # NEW: Git API client
        owner: str = None,      # NEW: Repository owner
        repo: str = None        # NEW: Repository name
    ):
        # Support both local and API-based indexing
        self.use_api = git_client is not None
        
        if self.use_api:
            self.git_client = git_client
            self.owner = owner
            self.repo = repo
            self.version = version
        else:
            # Existing local file system approach
            self.repo_path = Path(repo_path or settings.git_repo_path)
            self.version = version or settings.code_version
            self.repo = None
            self.commit_sha = self._get_commit_sha()
    
    def index_repository(self, languages: List[str] = None, force_full: bool = False):
        """Index repository (supports both local and API-based)"""
        if self.use_api:
            return self._index_repository_from_api(languages, force_full)
        else:
            return self._index_repository_from_local(languages, force_full)
    
    def _index_repository_from_api(self, languages, force_full):
        """NEW: Index repository using Git API"""
        # 1. Fetch repository tree
        tree = self.git_client.get_repository_tree(
            self.owner, self.repo, self.version
        )
        
        # 2. Filter code files
        code_files = self._filter_code_files(tree, languages)
        
        # 3. Fetch and index each file
        stats = {'total_files': 0, 'total_blocks': 0, 'errors': 0}
        
        for file_info in code_files:
            try:
                # Fetch file content via API
                file_data = self.git_client.get_file_content(
                    self.owner, self.repo, file_info['path'], self.version
                )
                
                # Parse code in-memory
                if file_info['path'].endswith('.py'):
                    blocks = self._index_python_code(
                        file_info['path'], file_data['content']
                    )
                elif file_info['path'].endswith('.java'):
                    blocks = self._index_java_code(
                        file_info['path'], file_data['content']
                    )
                
                stats['total_files'] += 1
                stats['total_blocks'] += len(blocks)
                
            except Exception as e:
                logger.error(f"Error indexing {file_info['path']}: {e}")
                stats['errors'] += 1
        
        return stats
    
    def _index_repository_from_local(self, languages, force_full):
        """EXISTING: Index repository from local file system"""
        # Keep existing implementation
        pass
    
    def _index_python_code(self, file_path: str, content: str) -> List[str]:
        """Parse Python code from string content"""
        # Similar to existing index_python_file but works with string content
        pass
    
    def _index_java_code(self, file_path: str, content: str) -> List[str]:
        """Parse Java code from string content"""
        # Similar to existing index_java_file but works with string content
        pass
```

---

## ✅ Phase 4: Update Tasks

### **4.1 Modify index_code_repository Task**

**File:** `src/services/tasks.py`

```python
@celery_app.task(name='tasks.index_code_repository', bind=True)
def index_code_repository(
    self,
    service_id: str = None,
    trigger_reason: str = 'manual',
    force_full: bool = False
):
    """Index code repository (supports both local and API-based)"""
    
    # Get service configuration
    service = db.query(Service).filter(Service.id == service_id).first()
    
    # Determine indexing method
    if service.git_provider and service.access_token_encrypted:
        # API-based indexing
        return _index_via_api(service, force_full)
    elif service.git_repo_path:
        # Local file system indexing
        return _index_via_local(service, force_full)
    else:
        raise ValueError("No indexing method configured")

def _index_via_api(service, force_full):
    """Index repository using Git API"""
    from src.integrations.git_client_factory import GitClientFactory
    from src.utils.encryption import decrypt_token
    
    # Decrypt access token
    token = decrypt_token(service.access_token_encrypted)
    
    # Create Git client
    git_client = GitClientFactory.create(service.git_provider, token)
    
    # Parse repository URL
    owner, repo = parse_repo_url(service.repository_url)
    
    # Get latest commit
    current_commit = git_client.get_latest_commit(owner, repo, service.git_branch)
    
    # Check if indexing needed
    if not force_full and current_commit == service.last_indexed_commit:
        return {"status": "skipped", "reason": "no changes"}
    
    # Create indexer with API client
    indexer = CodeIndexer(
        git_client=git_client,
        owner=owner,
        repo=repo,
        version=service.git_branch
    )
    
    # Run indexing
    stats = indexer.index_repository(languages=['python', 'java'], force_full=force_full)
    
    # Update service
    service.last_indexed_commit = current_commit
    service.last_indexed_at = datetime.utcnow()
    db.commit()
    
    return {
        'status': 'success',
        'commit_sha': current_commit,
        'files_indexed': stats['total_files'],
        'blocks_indexed': stats['total_blocks']
    }

def _index_via_local(service, force_full):
    """EXISTING: Index repository from local file system"""
    # Keep existing implementation
    pass
```

---

## ✅ Phase 5: Token Encryption

### **5.1 Create Encryption Utility**

**File:** `src/utils/encryption.py`

```python
"""
Utility for encrypting/decrypting access tokens
"""
from cryptography.fernet import Fernet
from src.config.settings import settings

# Load encryption key from environment
ENCRYPTION_KEY = settings.encryption_key.encode()
cipher = Fernet(ENCRYPTION_KEY)

def encrypt_token(token: str) -> str:
    """Encrypt access token for storage"""
    return cipher.encrypt(token.encode()).decode()

def decrypt_token(encrypted_token: str) -> str:
    """Decrypt access token for use"""
    return cipher.decrypt(encrypted_token.encode()).decode()
```

### **5.2 Update Settings**

**File:** `src/config/settings.py`

```python
class Settings(BaseSettings):
    # Existing settings...
    
    # NEW: Encryption key for access tokens
    encryption_key: str = Field(
        default=Fernet.generate_key().decode(),
        description="Encryption key for access tokens"
    )
```

### **5.3 Update .env**

```bash
# Add to .env file
ENCRYPTION_KEY=your-32-byte-base64-encoded-key-here
```

**Generate Key:**
```python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

---

## ✅ Phase 6: API Endpoints

### **6.1 Add Connection Test Endpoint**

**File:** `src/services/api_services.py`

```python
@router.post("/services/{service_id}/test-connection")
async def test_git_connection(
    service_id: str,
    db: Session = Depends(get_db)
):
    """Test Git API connection"""
    service = db.query(Service).filter(Service.id == service_id).first()
    
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    if not service.git_provider or not service.access_token_encrypted:
        raise HTTPException(status_code=400, detail="Git provider not configured")
    
    # Decrypt token
    token = decrypt_token(service.access_token_encrypted)
    
    # Create client
    git_client = GitClientFactory.create(service.git_provider, token)
    
    # Parse URL
    owner, repo = parse_repo_url(service.repository_url)
    
    # Test connection
    if service.git_provider == 'github':
        result = git_client.test_connection(owner, repo)
    else:  # gitlab
        project_path = f"{owner}/{repo}"
        result = git_client.test_connection(project_path)
    
    return result
```

### **6.2 Update Service Creation Endpoint**

**File:** `src/services/api_services.py`

```python
@router.post("/services")
async def create_service(
    service_data: dict,
    db: Session = Depends(get_db)
):
    """Create new service with Git configuration"""
    
    # Encrypt access token if provided
    if 'access_token' in service_data:
        access_token = service_data.pop('access_token')
        service_data['access_token_encrypted'] = encrypt_token(access_token)
    
    # Parse repository URL
    if 'repository_url' in service_data:
        owner, repo = parse_repo_url(service_data['repository_url'])
        service_data['repository_owner'] = owner
        service_data['repository_name'] = repo
        
        # Get GitLab project ID if needed
        if service_data.get('git_provider') == 'gitlab':
            token = decrypt_token(service_data['access_token_encrypted'])
            gitlab_client = GitLabClient(token)
            project_id = gitlab_client.get_project_id(owner, repo)
            service_data['repository_id'] = project_id
    
    # Create service
    service = Service(**service_data)
    db.add(service)
    db.commit()
    db.refresh(service)
    
    return service
```

---

## ✅ Phase 7: Frontend Updates

### **7.1 Update Service Form**

**File:** `frontend/src/pages/Settings.tsx`

```typescript
const ServiceConfigForm = () => {
  return (
    <Form layout="vertical">
      {/* Existing fields... */}
      
      <Form.Item
        label="Git Provider"
        name="git_provider"
        rules={[{ required: true }]}
      >
        <Select placeholder="Select provider">
          <Option value="github">GitHub</Option>
          <Option value="gitlab">GitLab</Option>
        </Select>
      </Form.Item>
      
      <Form.Item
        label="Repository URL"
        name="repository_url"
        rules={[{ required: true, type: 'url' }]}
      >
        <Input placeholder="https://github.com/org/repo" />
      </Form.Item>
      
      <Form.Item
        label="Branch"
        name="git_branch"
        rules={[{ required: true }]}
      >
        <Input placeholder="main" />
      </Form.Item>
      
      <Form.Item
        label="Access Token"
        name="access_token"
        rules={[{ required: true }]}
        extra="Token will be encrypted before storage"
      >
        <Input.Password placeholder="ghp_xxxxxxxxxxxx" />
      </Form.Item>
      
      <Button onClick={testConnection}>
        Test Connection
      </Button>
    </Form>
  );
};
```

### **7.2 Add Connection Test**

```typescript
const testConnection = async () => {
  try {
    const response = await servicesAPI.testConnection(serviceId);
    
    if (response.status === 'success') {
      message.success(`Connected to ${response.repository}`);
    } else {
      message.error(response.message);
    }
  } catch (error) {
    message.error('Connection test failed');
  }
};
```

---

## ✅ Phase 8: Testing

### **8.1 Create Test Script**

**File:** `scripts/test_api_indexing.py`

```python
"""
Test API-based code indexing
"""
import requests

BASE_URL = "http://localhost:8000/api/v1"

def test_github_indexing():
    # 1. Create service
    service_data = {
        "id": "test-github",
        "name": "Test GitHub Service",
        "repository_url": "https://github.com/org/repo",
        "git_branch": "main",
        "git_provider": "github",
        "access_token": "ghp_xxxxxxxxxxxx",
        "code_indexing_enabled": True
    }
    
    response = requests.post(f"{BASE_URL}/services", json=service_data)
    print(f"Create service: {response.status_code}")
    
    # 2. Test connection
    response = requests.post(f"{BASE_URL}/services/test-github/test-connection")
    print(f"Test connection: {response.json()}")
    
    # 3. Trigger indexing
    response = requests.post(
        f"{BASE_URL}/code-indexing/services/test-github/trigger?force_full=true"
    )
    print(f"Trigger indexing: {response.json()}")
    
    # 4. Check status
    response = requests.get(f"{BASE_URL}/code-indexing/services/test-github/status")
    print(f"Indexing status: {response.json()}")

if __name__ == "__main__":
    test_github_indexing()
```

**Run Test:**
```bash
python scripts/test_api_indexing.py
```

---

## ✅ Phase 9: Documentation

### **9.1 Update User Guide**

Create user-facing documentation:
- How to get GitHub/GitLab access tokens
- How to configure services
- How to test connections
- Troubleshooting guide

### **9.2 Update API Documentation**

Add to API docs:
- New service configuration fields
- Connection test endpoint
- Token security information

---

## 📊 Implementation Progress

### **Checklist:**

- [ ] Phase 1: Database Schema Updates
  - [ ] Update Service model
  - [ ] Create migration script
  - [ ] Run migration

- [ ] Phase 2: Git API Client Implementation
  - [ ] Create GitHub client
  - [ ] Create GitLab client
  - [ ] Create client factory

- [ ] Phase 3: Update Code Indexer
  - [ ] Modify CodeIndexer class
  - [ ] Add API-based indexing method
  - [ ] Add in-memory code parsing

- [ ] Phase 4: Update Tasks
  - [ ] Modify index_code_repository task
  - [ ] Add API-based indexing logic
  - [ ] Keep backward compatibility

- [ ] Phase 5: Token Encryption
  - [ ] Create encryption utility
  - [ ] Update settings
  - [ ] Generate encryption key

- [ ] Phase 6: API Endpoints
  - [ ] Add connection test endpoint
  - [ ] Update service creation
  - [ ] Update service configuration

- [ ] Phase 7: Frontend Updates
  - [ ] Update service form
  - [ ] Add connection test button
  - [ ] Add token input field

- [ ] Phase 8: Testing
  - [ ] Create test script
  - [ ] Test GitHub integration
  - [ ] Test GitLab integration

- [ ] Phase 9: Documentation
  - [ ] Update user guide
  - [ ] Update API docs
  - [ ] Create troubleshooting guide

---

## 🎯 Estimated Timeline

- **Phase 1-2**: 2-3 hours (Database + API clients)
- **Phase 3-4**: 3-4 hours (Code indexer + Tasks)
- **Phase 5**: 1 hour (Encryption)
- **Phase 6-7**: 2-3 hours (API + Frontend)
- **Phase 8-9**: 2 hours (Testing + Docs)

**Total: 10-13 hours**

---

## 🚀 Deployment

### **Environment Variables:**

```bash
# .env
ENCRYPTION_KEY=your-encryption-key-here
GITHUB_API_URL=https://api.github.com
GITLAB_API_URL=https://gitlab.com/api/v4
```

### **Docker:**

No changes needed - API-based indexing works in containers without volume mounts!

---

**Last Updated:** 2025-12-07  
**Status:** Ready for Implementation 🚀
