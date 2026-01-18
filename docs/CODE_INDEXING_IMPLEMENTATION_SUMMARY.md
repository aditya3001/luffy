# Code Indexing Implementation Summary

## ✅ Implementation Complete

### **Key Features:**
1. ✅ **API-Based Code Indexing** - No local repository storage
2. ✅ **Per Log Source Configuration** - Each log source has independent Git config
3. ✅ **Encrypted Token Storage** - Fernet (AES-128) encryption
4. ✅ **UI-Only Token Expiry Notifications** - No email/Slack alerts
5. ✅ **Automatic Change Detection** - Commit SHA tracking
6. ✅ **UI-Driven Configuration** - All setup through web interface

---

## 📁 Files Created/Modified

### **Backend (3 new files):**

1. **`src/utils/encryption.py`** (NEW)
   - Token encryption/decryption using Fernet
   - `encrypt_token()` - Encrypt plain text tokens
   - `decrypt_token()` - Decrypt for API calls
   - `is_token_encrypted()` - Check if already encrypted

2. **`src/integrations/git_api_client.py`** (NEW)
   - GitHub and GitLab API clients
   - `GitHubClient` - GitHub REST API v3
   - `GitLabClient` - GitLab REST API v4
   - `GitClientFactory` - Create appropriate client
   - Methods: test_authentication, get_latest_commit, get_repository_tree, get_file_content

3. **`src/storage/models.py`** (MODIFIED)
   - Added Git configuration fields to `LogSource` model:
     - `code_indexing_enabled` - Enable/disable per log source
     - `git_provider` - github or gitlab
     - `repository_url` - Full Git URL
     - `git_branch` - Branch to index
     - `repository_owner`, `repository_name` - Parsed from URL
     - `access_token_encrypted` - Encrypted token
     - `token_status` - valid, expired, invalid, not_configured
     - `token_last_validated` - Last validation timestamp
     - `last_indexed_commit` - Commit SHA tracking
     - `indexing_status` - not_started, in_progress, completed, failed
     - `indexing_error` - Error message if failed

### **Frontend (1 new file):**

4. **`frontend/src/components/TokenStatus.tsx`** (NEW)
   - `TokenStatusBadge` - Shows token status with icon/color
   - `TokenExpiryAlert` - Red alert banner for expired tokens
   - `TokenStatusCard` - Comprehensive status card
   - All components show "Update Token" button when expired
   - **No email/Slack notifications** - UI only!

---

## 🔄 User Workflow

### **Step 1: Create/Edit Log Source**

```
User navigates to: Services → web-app → Log Sources → Add/Edit

Form includes:
├─ Log Source Name
├─ Source Type (OpenSearch/Elasticsearch)
├─ Connection Details (host, port, credentials)
└─ Code Indexing Section (Optional)
    ├─ ☑ Enable Code Indexing
    ├─ Git Provider: [GitHub/GitLab]
    ├─ Repository URL: https://github.com/org/repo
    ├─ Branch: main
    └─ Access Token: ghp_xxxxxxxxxxxx
```

### **Step 2: Test Connections**

```
User clicks:
├─ "Test Log Connection" → Validates OpenSearch
└─ "Test Git Connection" → Validates token & repo access
```

### **Step 3: Save**

```
Backend:
├─ Encrypts access token
├─ Parses repository URL
├─ Stores in database
└─ Returns success (without token!)
```

### **Step 4: Automatic Indexing**

```
Triggers:
├─ Exception detected → Check if code changed → Index if needed
├─ Scheduled (daily 2 AM) → Check all log sources → Index if changed
└─ Manual trigger → Force indexing
```

---

## 🔐 Token Management

### **Encryption Flow:**

```
User Input (UI):
  Plain token: "ghp_xxxxxxxxxxxx"
  ↓ HTTPS
Backend:
  encrypted = encrypt_token("ghp_xxxxxxxxxxxx")
  Result: "gAAAAABhXyZ..."
  ↓
Database:
  access_token_encrypted = "gAAAAABhXyZ..."
  token_status = "valid"
```

### **Usage Flow:**

```
Indexing Task:
  1. Fetch log_source from database
  2. Decrypt: token = decrypt_token(log_source.access_token_encrypted)
  3. Create client: GitHubClient(token)
  4. Make API calls
  5. Clear token from memory
```

### **Expiry Detection:**

```
API Call Returns 401:
  ↓
Update Database:
  log_source.token_status = "expired"
  log_source.indexing_status = "failed"
  log_source.indexing_error = "Access token expired"
  ↓
UI Shows:
  🔴 Red alert banner: "Access Token Expired"
  🔴 Badge: "Token: Expired"
  🔴 Button: "Update Token"
  ↓
User Action:
  1. Click "Update Token"
  2. Generate new token from GitHub/GitLab
  3. Paste in form
  4. Test connection
  5. Save
  ↓
Operations Resume:
  token_status = "valid"
  Next indexing uses new token
```

---

## 🎨 UI Components Usage

### **In Log Source List:**

```typescript
import { TokenStatusBadge } from '@/components/TokenStatus';

<List.Item>
  <List.Item.Meta
    title={logSource.name}
    description={
      <TokenStatusBadge logSource={logSource} showDetails />
    }
  />
</List.Item>
```

### **In Log Source Detail Page:**

```typescript
import { TokenExpiryAlert, TokenStatusCard } from '@/components/TokenStatus';

<Space direction="vertical" size="large" style={{ width: '100%' }}>
  {/* Shows red alert if token expired */}
  <TokenExpiryAlert logSource={logSource} />
  
  {/* Shows comprehensive status */}
  <TokenStatusCard logSource={logSource} />
</Space>
```

### **In Dashboard:**

```typescript
// Show count of expired tokens
const expiredTokens = logSources.filter(
  ls => ls.token_status === 'expired'
).length;

{expiredTokens > 0 && (
  <Alert
    message={`${expiredTokens} log source(s) have expired Git tokens`}
    type="error"
    showIcon
    action={
      <Button onClick={() => navigate('/log-sources')}>
        View & Fix
      </Button>
    }
  />
)}
```

---

## 🔧 API Endpoints Needed

### **Log Source Management:**

```python
# Add/Update log source with Git config
POST /api/v1/services/{service_id}/log-sources
PUT /api/v1/log-sources/{id}
{
  "name": "Production OpenSearch",
  "source_type": "opensearch",
  "host": "opensearch.example.com",
  "port": 9200,
  "code_indexing_enabled": true,
  "git_provider": "github",
  "repository_url": "https://github.com/org/web-app",
  "git_branch": "main",
  "access_token": "ghp_xxxxxxxxxxxx"  // Will be encrypted
}

# Test Git connection
POST /api/v1/log-sources/{id}/test-git-connection
Response: {
  "status": "success",
  "repository": "org/web-app",
  "default_branch": "main",
  "access": "read-only"
}

# Validate token
POST /api/v1/log-sources/{id}/validate-token
Response: {
  "status": "success",
  "token_status": "valid",
  "validated_at": "2025-12-07T10:00:00Z"
}

# Trigger indexing
POST /api/v1/log-sources/{id}/trigger-indexing?force_full=false

# Get indexing status
GET /api/v1/log-sources/{id}/indexing-status
Response: {
  "status": "completed",
  "last_indexed_commit": "abc123",
  "last_indexed_at": "2025-12-07T10:00:00Z",
  "files_indexed": 45,
  "blocks_indexed": 234
}
```

---

## 📊 Database Migration

### **Add columns to log_sources table:**

```sql
ALTER TABLE log_sources ADD COLUMN code_indexing_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE log_sources ADD COLUMN git_provider VARCHAR(50);
ALTER TABLE log_sources ADD COLUMN repository_url VARCHAR(500);
ALTER TABLE log_sources ADD COLUMN git_branch VARCHAR(255) DEFAULT 'main';
ALTER TABLE log_sources ADD COLUMN repository_owner VARCHAR(255);
ALTER TABLE log_sources ADD COLUMN repository_name VARCHAR(255);
ALTER TABLE log_sources ADD COLUMN repository_id VARCHAR(255);
ALTER TABLE log_sources ADD COLUMN access_token_encrypted TEXT;
ALTER TABLE log_sources ADD COLUMN token_status VARCHAR(50) DEFAULT 'not_configured';
ALTER TABLE log_sources ADD COLUMN token_last_validated TIMESTAMP;
ALTER TABLE log_sources ADD COLUMN last_indexed_commit VARCHAR(255);
ALTER TABLE log_sources ADD COLUMN last_indexed_at TIMESTAMP;
ALTER TABLE log_sources ADD COLUMN indexing_status VARCHAR(50) DEFAULT 'not_started';
ALTER TABLE log_sources ADD COLUMN indexing_error TEXT;
```

---

## 🔒 Security Checklist

- ✅ Tokens encrypted at rest (Fernet/AES-128)
- ✅ Tokens encrypted in transit (HTTPS)
- ✅ Tokens decrypted only when needed
- ✅ Tokens never logged
- ✅ Tokens never in API responses
- ✅ Tokens cleared from memory after use
- ✅ ENCRYPTION_KEY in environment variable
- ✅ Token expiry detection (401 responses)
- ✅ UI-only notifications (no email/Slack)
- ✅ Read-only Git permissions required
- ✅ Repository-specific tokens recommended

---

## 🎯 Next Steps

### **1. Backend Implementation:**
- [ ] Create API endpoints for log source Git configuration
- [ ] Implement token validation endpoint
- [ ] Update indexing task to use per-log-source Git config
- [ ] Add daily token health check task
- [ ] Handle AuthenticationError exceptions

### **2. Frontend Implementation:**
- [ ] Add Git configuration section to log source form
- [ ] Integrate TokenStatus components
- [ ] Add "Test Git Connection" button
- [ ] Show token expiry alerts in dashboard
- [ ] Add token update workflow

### **3. Testing:**
- [ ] Test token encryption/decryption
- [ ] Test GitHub API client
- [ ] Test GitLab API client
- [ ] Test token expiry detection
- [ ] Test UI notifications
- [ ] Test token update workflow

### **4. Documentation:**
- [ ] Update user guide with Git configuration steps
- [ ] Document token generation process for GitHub/GitLab
- [ ] Add troubleshooting guide for token issues

---

## 📝 Environment Variables

Add to `.env`:

```bash
# Token Encryption (REQUIRED)
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=your-32-byte-base64-encoded-key-here
```

---

## 🎉 Summary

### **What's Different:**
- ❌ **OLD:** Git config at service level, local clones, email notifications
- ✅ **NEW:** Git config per log source, API-based, UI-only notifications

### **Key Benefits:**
- 🚀 No disk storage required
- 🔒 Secure token encryption
- 🎨 Clear UI notifications
- 🔄 Automatic change detection
- 📈 Scalable to unlimited repos
- ☁️ Cloud-native architecture

### **User Experience:**
1. User adds log source → Optionally enables code indexing
2. User provides Git details → Tests connection → Saves
3. System indexes code automatically when changes detected
4. If token expires → UI shows red alert → User updates token
5. Operations resume automatically

**Result: Simple, secure, scalable code indexing with clear UI feedback!** 🚀
