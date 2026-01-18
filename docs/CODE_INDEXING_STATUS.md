# Code Indexing - Implementation Status

## ✅ Completed

### **1. Backend Components**
- ✅ Updated `LogSource` model with Git configuration fields
- ✅ Created `src/utils/encryption.py` for token encryption/decryption
- ✅ Created `src/integrations/git_api_client.py` for GitHub/GitLab API
- ✅ Token encryption using Fernet (AES-128)
- ✅ Authentication error handling

### **2. Frontend Components**
- ✅ Added Git configuration section to log source form
- ✅ Created `TokenStatus.tsx` components for UI notifications
- ✅ Updated TypeScript types (`LogSource`, `LogSourceConfig`)
- ✅ Added "Code Indexing" column to log sources table
- ✅ Conditional form fields (show Git config only when enabled)
- ✅ Token status badges with icons and colors

### **3. UI Features**
- ✅ "Enable Code Indexing" toggle switch
- ✅ Git provider selection (GitHub/GitLab)
- ✅ Repository URL input with validation
- ✅ Branch name input
- ✅ Access token input (password field)
- ✅ "Test Git Connection" button placeholder
- ✅ Token status display in table
- ✅ Help link for token generation

---

## 🚧 Pending Implementation

### **1. Backend API Endpoints**
- ⏳ POST `/api/v1/log-sources` - Create with Git config
- ⏳ PUT `/api/v1/log-sources/{id}` - Update with Git config
- ⏳ POST `/api/v1/log-sources/{id}/test-git-connection` - Test connection
- ⏳ POST `/api/v1/log-sources/{id}/validate-token` - Validate token
- ⏳ POST `/api/v1/log-sources/{id}/trigger-indexing` - Trigger indexing
- ⏳ GET `/api/v1/log-sources/{id}/indexing-status` - Get status

### **2. Backend Logic**
- ⏳ Parse repository URL to extract owner/repo
- ⏳ Encrypt token before storing in database
- ⏳ Decrypt token when needed for API calls
- ⏳ Handle `AuthenticationError` for token expiry
- ⏳ Update `token_status` on API failures
- ⏳ Test Git connection implementation

### **3. Code Indexing Task**
- ⏳ Update `index_code_repository` task to use per-log-source config
- ⏳ Fetch Git config from `LogSource` model
- ⏳ Use `GitClientFactory` to create appropriate client
- ⏳ Fetch code via API (no local clones)
- ⏳ Track commit SHA for change detection
- ⏳ Update indexing status and errors

### **4. Database Migration**
- ⏳ Create migration script for new `log_sources` columns
- ⏳ Set default values for existing records
- ⏳ Test migration on development database

### **5. Frontend Integration**
- ⏳ Implement "Test Git Connection" button functionality
- ⏳ Show real-time connection test results
- ⏳ Display token expiry alerts on dashboard
- ⏳ Add TokenExpiryAlert to log source detail page
- ⏳ Handle form submission with Git config

---

## 📋 Current UI Flow

### **Creating Log Source with Code Indexing:**

```
1. User clicks "Add Log Source"
2. Fills log source details (name, type, host, port, etc.)
3. Toggles "Enable Code Indexing" switch ✅
4. Form expands to show Git configuration fields ✅
5. User selects Git provider (GitHub/GitLab) ✅
6. Enters repository URL ✅
7. Enters branch name ✅
8. Enters access token ✅
9. Clicks "Test Git Connection" (placeholder) ⏳
10. Clicks "Add Log Source" ⏳
11. Backend encrypts token and saves ⏳
```

### **Viewing Log Sources:**

```
1. User views log sources table
2. "Code Indexing" column shows status ✅
   - "Disabled" if not enabled
   - "Active" if token valid (green)
   - "Token Expired" if expired (red)
   - "Invalid Token" if invalid (red)
   - "Not Configured" if no token (gray)
3. Hover shows tooltip with error details ✅
```

### **Token Expiry Handling:**

```
1. Indexing task detects 401 error ⏳
2. Updates token_status = 'expired' ⏳
3. UI shows red "Token Expired" badge ✅
4. User clicks "Edit" on log source ⏳
5. Updates access token ⏳
6. Tests connection ⏳
7. Saves ⏳
8. Operations resume ⏳
```

---

## 🎨 What You Can See Now

### **In Log Source Form:**

When you click "Add Log Source" or "Edit", you'll see:

```
┌────────────────────────────────────────┐
│ Create Log Source                      │
├────────────────────────────────────────┤
│                                        │
│ Log Source Name: *                     │
│ [Production OpenSearch]                │
│                                        │
│ Source Type: *                         │
│ [OpenSearch ▼]                         │
│                                        │
│ Host: *          Port: *               │
│ [localhost]      [9200]                │
│                                        │
│ ... (other fields) ...                 │
│                                        │
│ ──────────────────────────────────── │
│ Code Indexing Configuration (Optional) │
│ ──────────────────────────────────── │
│                                        │
│ ☑ Enable Code Indexing                │
│                                        │
│ Git Provider: *                        │
│ [GitHub ▼]                             │
│                                        │
│ Repository URL: *                      │
│ [https://github.com/org/repo]          │
│                                        │
│ Branch: *                              │
│ [main]                                 │
│                                        │
│ Access Token: *                        │
│ [••••••••••••••]                       │
│ 📖 How to generate access token?      │
│                                        │
│ [Test Git Connection]                  │
│                                        │
│ [Add Log Source]  [Cancel]             │
└────────────────────────────────────────┘
```

### **In Log Sources Table:**

You'll see a new "Code Indexing" column:

```
| Name              | Type       | Host          | ... | Code Indexing      | Actions |
|-------------------|------------|---------------|-----|--------------------|---------|
| Production Logs   | OPENSEARCH | localhost:9200| ... | Disabled           | [Edit]  |
| Staging Logs      | OPENSEARCH | staging:9200  | ... | ✅ Active          | [Edit]  |
| Dev Logs          | OPENSEARCH | dev:9200      | ... | ❌ Token Expired   | [Edit]  |
```

---

## 🔧 Next Steps to Complete

### **Priority 1: Backend API (Required for functionality)**
1. Create log source API endpoints with Git config support
2. Implement token encryption in create/update endpoints
3. Implement test Git connection endpoint
4. Parse repository URL to extract owner/repo

### **Priority 2: Code Indexing Task**
1. Update task to fetch Git config from log source
2. Use GitClientFactory to create API client
3. Implement API-based code fetching
4. Handle authentication errors

### **Priority 3: Database Migration**
1. Create migration script
2. Test on development database
3. Apply to production

### **Priority 4: Frontend Integration**
1. Implement test connection functionality
2. Handle form submission
3. Show success/error messages
4. Add token expiry alerts

---

## 📝 Environment Setup Required

Add to `.env`:

```bash
# Token Encryption Key (REQUIRED)
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=your-32-byte-base64-encoded-key-here
```

---

## ✨ Summary

**What's Working:**
- ✅ UI form with Git configuration fields
- ✅ Conditional display (only when code indexing enabled)
- ✅ Token status display in table
- ✅ TypeScript types updated
- ✅ Backend models updated
- ✅ Encryption utilities created
- ✅ Git API clients created

**What's Needed:**
- ⏳ Backend API endpoints
- ⏳ Code indexing task updates
- ⏳ Database migration
- ⏳ Frontend API integration
- ⏳ Testing and validation

**Current Status:** UI is ready, backend implementation needed to make it functional.
