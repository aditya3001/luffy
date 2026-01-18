# Code Indexing - Quick Reference

## 🎯 Overview

**What:** API-based code indexing per log source  
**Where:** Git configuration in log source settings  
**Security:** Encrypted tokens, UI-only expiry notifications  
**Storage:** No local clones, all via GitHub/GitLab API  

---

## 🚀 Quick Start

### 1. Add Log Source with Git Config

```
Navigate: Services → web-app → Log Sources → Add

Fill form:
├─ Name: Production OpenSearch
├─ Type: OpenSearch
├─ Host: opensearch.example.com
└─ ☑ Enable Code Indexing
    ├─ Provider: GitHub
    ├─ URL: https://github.com/org/web-app
    ├─ Branch: main
    └─ Token: ghp_xxxxxxxxxxxx

Click: Test Git Connection → Save
```

### 2. Token Expires

```
UI shows:
🔴 Alert: "Access Token Expired"
🔴 Badge: "Token: Expired"
🔴 Button: "Update Token"

Action:
1. Click "Update Token"
2. Generate new token from GitHub
3. Paste → Test → Save
4. Done! ✅
```

---

## 📁 Key Files

| File | Purpose |
|------|---------|
| `src/utils/encryption.py` | Token encryption/decryption |
| `src/integrations/git_api_client.py` | GitHub/GitLab API clients |
| `src/storage/models.py` | LogSource model with Git fields |
| `frontend/src/components/TokenStatus.tsx` | UI notifications |

---

## 🔐 Token Management

### Encryption:
```python
from src.utils.encryption import encrypt_token, decrypt_token

# Encrypt before storing
encrypted = encrypt_token("ghp_xxxxxxxxxxxx")

# Decrypt for API calls
token = decrypt_token(encrypted)
```

### Status Values:
- `valid` - Token works ✅
- `expired` - Token expired, update needed ❌
- `invalid` - Token invalid, update needed ❌
- `not_configured` - No token set ⚪

---

## 🎨 UI Components

### Show Token Status:
```typescript
import { TokenStatusBadge } from '@/components/TokenStatus';

<TokenStatusBadge logSource={logSource} showDetails />
```

### Show Expiry Alert:
```typescript
import { TokenExpiryAlert } from '@/components/TokenStatus';

<TokenExpiryAlert logSource={logSource} />
```

### Show Status Card:
```typescript
import { TokenStatusCard } from '@/components/TokenStatus';

<TokenStatusCard logSource={logSource} />
```

---

## 🔧 API Endpoints

```bash
# Test Git connection
POST /api/v1/log-sources/{id}/test-git-connection

# Validate token
POST /api/v1/log-sources/{id}/validate-token

# Trigger indexing
POST /api/v1/log-sources/{id}/trigger-indexing

# Get status
GET /api/v1/log-sources/{id}/indexing-status
```

---

## 📊 Database Fields

### LogSource Model:
```python
code_indexing_enabled = Boolean
git_provider = String  # github, gitlab
repository_url = String
git_branch = String
access_token_encrypted = Text  # ENCRYPTED!
token_status = String  # valid, expired, invalid
last_indexed_commit = String  # SHA tracking
indexing_status = String  # not_started, in_progress, completed, failed
```

---

## ⚙️ Environment Setup

```bash
# .env file
ENCRYPTION_KEY=your-32-byte-base64-key

# Generate key:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## 🔄 Indexing Flow

```
Exception Detected
  ↓
Check if code changed (compare commit SHAs)
  ↓
If changed → Trigger indexing
  ↓
Fetch files via GitHub/GitLab API
  ↓
Parse code → Generate embeddings
  ↓
Store in vector DB
  ↓
Update last_indexed_commit
```

---

## 🐛 Troubleshooting

### Token Expired:
- **Symptom:** Red alert in UI, indexing fails
- **Fix:** Update token in log source settings

### Connection Failed:
- **Symptom:** "Test Connection" fails
- **Check:** Token permissions, repository access, URL format

### Indexing Fails:
- **Symptom:** indexing_status = "failed"
- **Check:** Token status, API rate limits, network connectivity

---

## 📝 Checklist

### Initial Setup:
- [ ] Set ENCRYPTION_KEY in .env
- [ ] Run database migration
- [ ] Add log source with Git config
- [ ] Test Git connection
- [ ] Verify indexing works

### Token Rotation:
- [ ] Generate new token from GitHub/GitLab
- [ ] Update in log source settings
- [ ] Test connection
- [ ] Verify indexing resumes

### Monitoring:
- [ ] Check token status badges
- [ ] Monitor indexing status
- [ ] Review indexing errors
- [ ] Validate last indexed commit

---

## 🎯 Key Points

✅ **Per Log Source** - Each log source has independent Git config  
✅ **UI Only** - Token expiry shown in UI, no email/Slack  
✅ **Encrypted** - Tokens encrypted at rest with Fernet  
✅ **API-Based** - No local repository clones  
✅ **Automatic** - Change detection via commit SHA tracking  
✅ **Secure** - Tokens never logged or exposed  

---

**Need Help?** See `CODE_INDEXING_IMPLEMENTATION_SUMMARY.md` for detailed implementation guide.
