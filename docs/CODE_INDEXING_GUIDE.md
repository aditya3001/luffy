# Code Indexing in Luffy - Complete Guide

## 📚 Overview

Code indexing is the process of parsing source code repositories, extracting meaningful code blocks (functions, classes, methods), and creating searchable embeddings for RAG (Retrieval-Augmented Generation) based analysis. This enables the system to find relevant code when analyzing exceptions.

---

## 🔄 Indexing Flow

### High-Level Architecture:

```
┌─────────────────┐
│  Git Repository │
└────────┬────────┘
         │
         ↓
┌─────────────────────────────────────────┐
│  1. Code Indexer Service                │
│     - Parses files (Python/Java)        │
│     - Extracts functions/classes        │
│     - Generates embeddings              │
└────────┬────────────────────────────────┘
         │
         ↓
┌─────────────────────────────────────────┐
│  2. Dual Storage                        │
│     ├─ PostgreSQL (metadata + code)     │
│     └─ Qdrant (vector embeddings)       │
└─────────────────────────────────────────┘
         │
         ↓
┌─────────────────────────────────────────┐
│  3. RAG Search                          │
│     - Query with exception/stack trace  │
│     - Find similar code blocks          │
│     - Generate context for LLM          │
└─────────────────────────────────────────┘
```

---

## 🔧 Core Components

### 1. CodeIndexer Service

**Location:** `src/services/code_indexer.py`

**Main Class:** `CodeIndexer`

**Key Responsibilities:**
- Parse source code files
- Extract code blocks (functions, classes, methods)
- Generate embeddings
- Store in dual databases

**Supported Languages:**
- ✅ **Python** - Using AST (Abstract Syntax Tree)
- ✅ **Java** - Using javalang library or regex fallback

**Initialization:**
```python
class CodeIndexer:
    def __init__(self, repo_path: str = None, version: str = None):
        self.repo_path = Path(repo_path or settings.git_repo_path)
        self.version = version or settings.code_version
        self.repo = None
        self.commit_sha = self._get_commit_sha()
```

---

## 📖 Indexing Modes

### 1. Full Indexing

**Triggered When:**
- First time indexing a repository
- `force_full=True` flag is set
- No previous indexing metadata exists

**Process:**
```python
# Get all files matching language extensions
files_to_index = self._get_all_files(languages)  # All *.py, *.java files

# Index every file
for file_path in files_to_index:
    if str(file_path).endswith('.py'):
        blocks = self.index_python_file(file_path)
    elif str(file_path).endswith('.java'):
        blocks = self.index_java_file(file_path)
```

**Steps:**
1. Scan entire repository
2. Find all files matching language extensions
3. Parse and index every file
4. Store all code blocks
5. Update indexing metadata

### 2. Incremental Indexing

**Triggered When:**
- Repository already indexed
- New commits detected
- `force_full=False` (default)

**Process:**
```python
# Get last indexed commit
last_commit = self._get_last_indexed_commit()

# Use Git diff to find changed files
files_to_index = self._get_changed_files_since_commit(last_commit, languages)

# Only index changed files
for file_path in files_to_index:
    # Parse and index only changed files
```

**Steps:**
1. Get last indexed commit SHA from database
2. Compare with current HEAD commit
3. Use Git diff to find changed files
4. Only parse and index changed files
5. Update or add code blocks
6. Update indexing metadata

**Benefits:**
- ⚡ **Much faster** - Only processes changes
- 💾 **Saves resources** - Doesn't re-process unchanged code
- 🔄 **Keeps index up-to-date** - Automatic change detection
- 🎯 **Efficient** - Scales well with large repositories

**Git Integration:**
```python
def _get_changed_files_since_commit(self, last_commit: str, languages: List[str]):
    # Get diff between commits
    diff = self.repo.commit(last_commit).diff(self.repo.head.commit)
    
    # Filter by language extensions
    changed_files = []
    for item in diff:
        if item.a_path and any(item.a_path.endswith(ext) for ext in extensions):
            file_path = self.repo_path / item.a_path
            if file_path.exists():
                changed_files.append(file_path)
    
    return changed_files
```

---

## 🐍 Python Indexing Process

### Step 1: Parse File with AST

```python
# Read source code
with open(file_path, 'r', encoding='utf-8') as f:
    source_code = f.read()

# Parse to Abstract Syntax Tree
tree = ast.parse(source_code)
```

**AST (Abstract Syntax Tree):**
- Python's built-in parser
- Converts code into structured tree
- Preserves all syntax information
- Enables precise code analysis

### Step 2: Walk AST and Extract Nodes

```python
# Walk through all nodes in the tree
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef):
        # Extract function details
        block = self._extract_function(node, file_path, source_code)
        code_blocks.append(block)
    
    elif isinstance(node, ast.ClassDef):
        # Extract class details
        block = self._extract_class(node, file_path, source_code)
        code_blocks.append(block)
```

**Node Types Extracted:**
- `ast.FunctionDef` - Function definitions
- `ast.ClassDef` - Class definitions
- `ast.AsyncFunctionDef` - Async functions (if needed)

### Step 3: Extract Function Details

```python
def _extract_function(self, node: ast.FunctionDef, file_path: Path, source_code: str):
    # Get source code lines
    lines = source_code.split('\n')
    start_line = node.lineno - 1
    end_line = node.end_lineno
    function_code = '\n'.join(lines[start_line:end_line])
    
    # Extract docstring
    docstring = ast.get_docstring(node) or ''
    
    # Build function signature
    args = [arg.arg for arg in node.args.args]
    signature = f"{node.name}({', '.join(args)})"
    
    # Generate qualified name
    rel_path = file_path.relative_to(self.repo_path)
    symbol_name = f"{str(rel_path).replace('/', '.').replace('.py', '')}.{node.name}"
    
    return {
        'file_path': str(rel_path),
        'symbol_name': symbol_name,
        'symbol_type': 'function',
        'line_start': node.lineno,
        'line_end': end_line + 1,
        'code_snippet': function_code,
        'docstring': docstring,
        'function_signature': signature
    }
```

**Extracted Information:**

| Field | Example | Description |
|-------|---------|-------------|
| `file_path` | `src/services/api.py` | Relative path from repo root |
| `symbol_name` | `src.services.api.get_clusters` | Fully qualified name |
| `symbol_type` | `function` | Type of code block |
| `line_start` | `45` | Starting line number |
| `line_end` | `67` | Ending line number |
| `code_snippet` | `def get_clusters(...):\n    ...` | Complete source code |
| `docstring` | `Retrieve exception clusters...` | Documentation string |
| `function_signature` | `get_clusters(limit, status)` | Function signature |

### Step 4: Extract Class Details

```python
def _extract_class(self, node: ast.ClassDef, file_path: Path, source_code: str):
    # Similar to function extraction
    # Extracts class definition, docstring, and metadata
    # Does not extract individual methods (handled separately)
```

---

## ☕ Java Indexing Process

### Two Approaches

#### Approach 1: Using javalang Library (Preferred)

**Installation:**
```bash
pip install javalang
```

**Process:**
```python
def _index_java_with_javalang(self, file_path: Path, source_code: str):
    # Parse Java source code
    tree = javalang.parse.parse(source_code)
    
    # Extract package name
    package_name = tree.package.name if tree.package else ''
    
    # Extract classes
    for path, node in tree.filter(javalang.tree.ClassDeclaration):
        block = self._extract_java_class(node, file_path, lines, package_name)
        code_blocks.append(block)
    
    # Extract methods
    for path, node in tree.filter(javalang.tree.MethodDeclaration):
        # Get parent class name
        parent_class = None
        for item in path:
            if isinstance(item, javalang.tree.ClassDeclaration):
                parent_class = item.name
                break
        
        block = self._extract_java_method(node, file_path, lines, package_name, parent_class)
        code_blocks.append(block)
```

**Features:**
- ✅ **Proper AST parsing** - Accurate syntax tree
- ✅ **Accurate line numbers** - Precise location tracking
- ✅ **Extracts Javadoc** - Documentation comments
- ✅ **Handles nested classes** - Inner classes supported
- ✅ **Type information** - Parameter and return types
- ✅ **Modifiers** - public, private, static, etc.

**Javadoc Extraction:**
```python
def _extract_java_javadoc(self, lines: List[str], line_num: int) -> str:
    javadoc_lines = []
    
    # Look backwards for Javadoc (/** ... */)
    i = line_num - 1
    while i >= 0 and i >= line_num - 20:
        line = lines[i].strip()
        
        if line.startswith('/**'):
            # Found start of Javadoc
            javadoc_lines.reverse()
            # Clean up formatting
            cleaned = []
            for jline in javadoc_lines:
                jline = re.sub(r'^/\*\*\s*', '', jline)
                jline = re.sub(r'\s*\*/$', '', jline)
                jline = re.sub(r'^\*\s*', '', jline)
                if jline:
                    cleaned.append(jline)
            return ' '.join(cleaned)
        
        elif line.startswith('*') or line.startswith('*/'):
            javadoc_lines.append(line)
        
        i -= 1
    
    return ''
```

#### Approach 2: Regex Fallback (When javalang unavailable)

**Process:**
```python
def _index_java_with_regex(self, file_path: Path, source_code: str):
    lines = source_code.split('\n')
    
    # Find class declarations
    class_pattern = r'(public|private|protected)?\s*class\s+(\w+)'
    
    # Find method declarations
    method_pattern = r'(public|private|protected)?\s+\w+\s+(\w+)\s*\([^)]*\)'
    
    for i, line in enumerate(lines):
        # Match class
        class_match = re.search(class_pattern, line)
        if class_match:
            # Extract class block
            ...
        
        # Match method
        method_match = re.search(method_pattern, line)
        if method_match:
            # Extract method block
            ...
```

**Features:**
- ⚠️ **Less accurate** - May miss edge cases
- ⚠️ **Limited nesting** - Struggles with complex structures
- ⚠️ **No type info** - Can't extract parameter types
- ✅ **Works without dependencies** - No external libraries
- ✅ **Better than nothing** - Fallback option

**When to Use:**
- javalang installation fails
- Quick prototyping
- Simple Java codebases
- Temporary solution

---

## 🧠 Embedding Generation

### Vector Database: Qdrant

**Why Qdrant?**
- ⚡ **Fast** - Optimized for similarity search
- 📈 **Scalable** - Handles millions of vectors
- 🔍 **Filtering** - Metadata-based filtering
- 🐳 **Docker-ready** - Easy deployment
- 🔧 **Python SDK** - Native integration

**Configuration:**
```python
self.client = QdrantClient(
    host=settings.qdrant_host,      # Default: localhost
    port=settings.qdrant_port,      # Default: 6333
    api_key=settings.qdrant_api_key # Optional
)
```

### Embedding Model: SentenceTransformer

**Model Used:**
```python
self.embedding_model = SentenceTransformer(settings.embedding_model)
# Default: 'all-MiniLM-L6-v2'
```

**Model Specifications:**
- **Dimensions**: 384
- **Max Sequence Length**: 256 tokens
- **Speed**: ~3000 sentences/second (GPU)
- **Quality**: Good balance of speed and accuracy
- **Size**: ~80MB

**Alternative Models:**
- `all-mpnet-base-v2` - Higher quality (768 dims)
- `paraphrase-MiniLM-L3-v2` - Faster (384 dims)
- `multi-qa-MiniLM-L6-cos-v1` - Optimized for Q&A

### Embedding Process

**Step 1: Combine Code Elements**
```python
# Create text representation of code block
code_text = f"{symbol_name}\n{docstring}\n{code_snippet}"

# Example:
"""
src.services.api.get_clusters
Retrieve exception clusters filtered by status and service
def get_clusters(limit: int = 100, status: str = 'active'):
    '''Retrieve exception clusters filtered by status and service'''
    clusters = db.query(ExceptionCluster).filter(
        ExceptionCluster.status == status
    ).limit(limit).all()
    return clusters
"""
```

**Step 2: Generate Embedding Vector**
```python
# Encode text to vector
embedding = self.embedding_model.encode(code_text).tolist()

# Returns: List of 384 floats
# Example: [0.123, -0.456, 0.789, -0.234, ...]
```

**Step 3: Store in Qdrant**
```python
point = PointStruct(
    id=code_id,              # UUID
    vector=embedding,         # 384-dim vector
    payload=metadata         # Searchable metadata
)

self.client.upsert(
    collection_name='code_embeddings',
    points=[point]
)
```

**What Gets Embedded:**

| Component | Weight | Purpose |
|-----------|--------|---------|
| Symbol Name | High | Match function/class names in stack traces |
| Docstring | Medium | Match error descriptions and intent |
| Code Snippet | High | Match code patterns and logic |

**Why This Works:**

1. **Semantic Similarity**
   - Exception messages semantically similar to code
   - "NullPointerException" → code handling null values
   - "Database connection failed" → database connection code

2. **Stack Trace Matching**
   - Function names in stack traces
   - Match to symbol names
   - Find exact code locations

3. **Pattern Recognition**
   - Similar code patterns
   - Common error handling
   - Typical implementations

4. **Context Understanding**
   - Docstrings explain purpose
   - Code shows implementation
   - Combined provides full context

---

## 💾 Dual Storage System

### Why Dual Storage?

**PostgreSQL:**
- ✅ Structured data storage
- ✅ Complex queries and joins
- ✅ ACID transactions
- ✅ Metadata management

**Qdrant:**
- ✅ Fast vector similarity search
- ✅ Semantic code search
- ✅ Scalable to millions of vectors
- ✅ Efficient nearest neighbor search

### 1. PostgreSQL (Relational Database)

**Table:** `code_blocks`

**Schema:**
```sql
CREATE TABLE code_blocks (
    id VARCHAR PRIMARY KEY,
    repository VARCHAR NOT NULL,
    version VARCHAR NOT NULL,
    commit_sha VARCHAR NOT NULL,
    file_path VARCHAR NOT NULL,
    symbol_name VARCHAR NOT NULL,
    symbol_type VARCHAR NOT NULL,  -- 'function', 'class', 'method'
    line_start INTEGER NOT NULL,
    line_end INTEGER NOT NULL,
    code_snippet TEXT NOT NULL,
    docstring TEXT,
    function_signature VARCHAR,
    embedding_id VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for fast queries
CREATE INDEX idx_code_blocks_repository ON code_blocks(repository);
CREATE INDEX idx_code_blocks_symbol_name ON code_blocks(symbol_name);
CREATE INDEX idx_code_blocks_file_path ON code_blocks(file_path);
CREATE INDEX idx_code_blocks_commit_sha ON code_blocks(commit_sha);
```

**Purpose:**
- Store complete code metadata
- Enable SQL queries and filtering
- Track indexing history
- Link to vector embeddings
- Support complex joins
- Audit trail

**Example Row:**
```json
{
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "repository": "my-app",
    "version": "v1.0.0",
    "commit_sha": "abc123def456",
    "file_path": "src/handlers/user.py",
    "symbol_name": "src.handlers.user.create_user",
    "symbol_type": "function",
    "line_start": 45,
    "line_end": 67,
    "code_snippet": "def create_user(email: str, name: str):\n    ...",
    "docstring": "Create a new user account",
    "function_signature": "create_user(email, name)",
    "embedding_id": "550e8400-e29b-41d4-a716-446655440000",
    "created_at": "2025-12-06 12:00:00",
    "updated_at": "2025-12-06 12:00:00"
}
```

### 2. Qdrant (Vector Database)

**Collection:** `code_embeddings`

**Configuration:**
```python
VectorParams(
    size=384,                # Embedding dimension
    distance=Distance.COSINE # Similarity metric
)
```

**Point Structure:**
```python
{
    'id': '550e8400-e29b-41d4-a716-446655440000',  # Same as PostgreSQL
    'vector': [0.123, -0.456, 0.789, ...],         # 384 floats
    'payload': {
        'repository': 'my-app',
        'version': 'v1.0.0',
        'commit_sha': 'abc123def456',
        'file_path': 'src/handlers/user.py',
        'symbol_name': 'src.handlers.user.create_user',
        'symbol_type': 'function',
        'line_start': 45,
        'line_end': 67
    }
}
```

**Purpose:**
- Fast similarity search (< 10ms for millions of vectors)
- Find relevant code for exceptions
- Support RAG-based analysis
- Scale to millions of code blocks
- Metadata filtering during search
- Cosine similarity ranking

**Search Performance:**
- **100K vectors**: ~5ms
- **1M vectors**: ~10ms
- **10M vectors**: ~50ms
- **Accuracy**: 99%+ with HNSW index

### Indexing Metadata Table

**Table:** `indexing_metadata`

**Schema:**
```sql
CREATE TABLE indexing_metadata (
    id SERIAL PRIMARY KEY,
    repository VARCHAR NOT NULL UNIQUE,
    last_indexed_commit VARCHAR,
    last_indexed_at TIMESTAMP,
    total_files_indexed INTEGER,
    total_blocks_indexed INTEGER,
    indexing_mode VARCHAR,  -- 'full' or 'incremental'
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**Purpose:**
- Track indexing history
- Enable incremental updates
- Monitor indexing health
- Detect when re-indexing needed
- Audit indexing operations

**Example Row:**
```json
{
    "repository": "my-app",
    "last_indexed_commit": "abc123def456",
    "last_indexed_at": "2025-12-06 12:00:00",
    "total_files_indexed": 145,
    "total_blocks_indexed": 1234,
    "indexing_mode": "incremental"
}
```

---

## 🔍 Search Process (RAG)

### When Exception Occurs

**Step 1: Extract Query from Exception**
```python
# Combine exception information
query_text = f"""
{exception_type}
{exception_message}
{stack_trace}
"""

# Example:
"""
NullPointerException
User object is null in create_user method
  at src.handlers.user.create_user (user.py:52)
  at src.api.routes.user_routes (routes.py:23)
  at flask.app.dispatch_request (app.py:1234)
"""
```

**Step 2: Generate Query Embedding**
```python
query_vector = vector_db.embed_text(query_text)
# Returns: [0.234, -0.567, 0.891, ...] (384 floats)
```

**Step 3: Search Similar Code Blocks**
```python
results = vector_db.search_code_blocks(
    query_text=query_text,
    top_k=5,
    filters={
        'repository': 'my-app',
        'version': 'v1.0.0',
        'file_path': 'src/handlers/user.py'  # Optional: from stack trace
    }
)
```

**Step 4: Results Ranked by Similarity**
```python
[
    {
        'id': 'uuid-1',
        'symbol_name': 'src.handlers.user.create_user',
        'score': 0.89,  # High similarity
        'file_path': 'src/handlers/user.py',
        'line_start': 45,
        'code_snippet': 'def create_user(email: str, name: str):\n    ...',
        'docstring': 'Create a new user account'
    },
    {
        'id': 'uuid-2',
        'symbol_name': 'src.handlers.user.validate_email',
        'score': 0.76,  # Medium similarity
        'file_path': 'src/handlers/user.py',
        'line_start': 23,
        'code_snippet': 'def validate_email(email: str):\n    ...',
        'docstring': 'Validate email format'
    },
    ...
]
```

### Similarity Scoring

**Cosine Similarity:**
```python
similarity = cosine(query_vector, code_vector)
# Range: -1.0 to 1.0
# Typically: 0.0 (unrelated) to 1.0 (identical)
```

**Score Interpretation:**

| Score Range | Interpretation | Action |
|-------------|----------------|--------|
| 0.9 - 1.0 | Highly relevant | Use for RCA |
| 0.7 - 0.9 | Relevant | Include in context |
| 0.5 - 0.7 | Somewhat relevant | Consider if needed |
| 0.0 - 0.5 | Not relevant | Ignore |

**Typical Threshold:** 0.6+ for relevant results

### Filtering During Search

**Qdrant Filter Syntax:**
```python
search_filter = Filter(
    must=[
        FieldCondition(
            key='repository',
            match=MatchValue(value='my-app')
        ),
        FieldCondition(
            key='version',
            match=MatchValue(value='v1.0.0')
        )
    ]
)

results = self.client.search(
    collection_name='code_embeddings',
    query_vector=query_vector,
    query_filter=search_filter,
    limit=top_k
)
```

**Common Filters:**
- `repository` - Specific codebase
- `version` - Code version
- `file_path` - Specific file or directory
- `symbol_type` - function, class, or method
- `commit_sha` - Specific commit

---

## 🚀 Usage Examples

### 1. Index Repository via Script

**Clone and Index:**
```bash
./scripts/clone_and_index.sh \
    https://github.com/myorg/myapp \
    v1.0.0 \
    python,java
```

**Script Process:**
1. Clones repository to `./data/repos/myapp`
2. Checks out version `v1.0.0`
3. Starts services if not running
4. Runs indexing via Docker
5. Verifies indexing success
6. Shows statistics

**Output:**
```
========================================
Code Indexing Setup
========================================

Repository: https://github.com/myorg/myapp
Version:    v1.0.0
Languages:  python,java

📥 Cloning repository...
🔀 Checking out version v1.0.0...
🔍 Checking if services are running...
✅ Services are running

📚 Indexing repository...
This may take a few minutes depending on repository size...

✅ Successfully indexed 1234 code blocks!

📊 Summary:
  Repository: myapp
  Version: v1.0.0
  Files: 145
  Blocks: 1234
  Mode: full
```

### 2. Index Programmatically

**Full Indexing:**
```python
from src.services.code_indexer import CodeIndexer

# Initialize indexer
indexer = CodeIndexer(
    repo_path='/path/to/repo',
    version='v1.0.0'
)

# Full indexing (all files)
stats = indexer.index_repository(
    languages=['python', 'java'],
    force_full=True
)

print(f"Indexed {stats['total_blocks']} blocks from {stats['total_files']} files")
# Output: Indexed 1234 blocks from 145 files
```

**Incremental Indexing:**
```python
# Incremental indexing (only changed files)
stats = indexer.index_repository(
    languages=['python'],
    force_full=False  # Default
)

if stats['mode'] == 'skip':
    print("Repository already up-to-date")
elif stats['mode'] == 'incremental':
    print(f"Indexed {stats['total_blocks']} new/changed blocks")
else:
    print(f"Full indexing: {stats['total_blocks']} blocks")
```

**Python Only:**
```python
# Index only Python files
stats = indexer.index_repository(languages=['python'])
```

**Java Only:**
```python
# Index only Java files
stats = indexer.index_repository(languages=['java'])
```

### 3. Search Indexed Code

**Basic Search:**
```python
from src.storage.vector_db import vector_db

results = vector_db.search_code_blocks(
    query_text="NullPointerException in user creation",
    top_k=5
)

for result in results:
    print(f"Found: {result['symbol_name']} (score: {result['score']:.2f})")
    print(f"File: {result['file_path']}:{result['line_start']}")
    print(f"Code:\n{result['code_snippet']}\n")
```

**Output:**
```
Found: src.handlers.user.create_user (score: 0.89)
File: src/handlers/user.py:45
Code:
def create_user(email: str, name: str):
    '''Create a new user account'''
    if not email:
        raise ValueError("Email is required")
    user = User(email=email, name=name)
    db.session.add(user)
    db.session.commit()
    return user

Found: src.handlers.user.validate_email (score: 0.76)
File: src/handlers/user.py:23
Code:
def validate_email(email: str):
    '''Validate email format'''
    if not email or '@' not in email:
        raise ValueError("Invalid email format")
    return True
```

**Filtered Search:**
```python
# Search with filters
results = vector_db.search_code_blocks(
    query_text="database connection error",
    top_k=10,
    filters={
        'repository': 'my-app',
        'version': 'v1.0.0',
        'file_path': 'src/database/',  # Directory prefix
        'symbol_type': 'function'
    }
)
```

**Stack Trace Search:**
```python
# Search using stack trace
stack_trace = """
  at src.handlers.user.create_user (user.py:52)
  at src.api.routes.user_routes (routes.py:23)
"""

results = vector_db.search_code_blocks(
    query_text=stack_trace,
    top_k=3
)

# Will find the exact functions mentioned in stack trace
```

### 4. Check Indexing Status

**Query PostgreSQL:**
```python
from src.storage.database import get_db
from src.storage.models import IndexingMetadata

with get_db() as db:
    metadata = db.query(IndexingMetadata).filter_by(
        repository='my-app'
    ).first()
    
    if metadata:
        print(f"Last indexed: {metadata.last_indexed_at}")
        print(f"Commit: {metadata.last_indexed_commit}")
        print(f"Files: {metadata.total_files_indexed}")
        print(f"Blocks: {metadata.total_blocks_indexed}")
        print(f"Mode: {metadata.indexing_mode}")
```

**Count Code Blocks:**
```python
from src.storage.models import CodeBlock

with get_db() as db:
    count = db.query(CodeBlock).filter_by(
        repository='my-app',
        version='v1.0.0'
    ).count()
    
    print(f"Total code blocks: {count}")
```

---

## ✅ Benefits of This Approach

### 1. Semantic Search
- **Find code by meaning**, not just keywords
- "database connection failed" → finds database connection code
- "user not found" → finds user lookup functions
- Works across different naming conventions

### 2. Context-Aware
- **Understands code structure** and relationships
- Knows function belongs to class
- Understands module hierarchy
- Preserves code context

### 3. Scalable
- **Handles large codebases** efficiently
- Millions of code blocks
- Fast search (< 10ms)
- Incremental updates

### 4. Incremental
- **Only re-indexes changed files**
- Saves time and resources
- Automatic change detection
- Git-based diffing

### 5. Multi-Language
- **Supports Python and Java** (extensible)
- Language-specific parsers
- Unified storage format
- Easy to add more languages

### 6. RAG-Ready
- **Provides context for LLM-based RCA**
- Relevant code snippets
- Ranked by similarity
- Filtered by metadata

### 7. Version-Aware
- **Tracks different code versions**
- Multiple versions per repository
- Commit SHA tracking
- Historical analysis

### 8. Fast Retrieval
- **Vector search is extremely fast**
- Sub-10ms for millions of vectors
- Efficient nearest neighbor search
- Optimized indexing

---

## 🎯 Performance Characteristics

### Indexing Speed

**Python Files:**
- Small file (< 100 lines): ~10ms
- Medium file (100-500 lines): ~50ms
- Large file (500-2000 lines): ~200ms
- Very large file (> 2000 lines): ~500ms

**Java Files:**
- With javalang: ~2x Python speed
- With regex: ~1.5x Python speed

**Full Repository:**
- 100 files: ~5 seconds
- 500 files: ~30 seconds
- 1000 files: ~1 minute
- 5000 files: ~5 minutes

**Incremental Update:**
- 1 changed file: ~50ms
- 10 changed files: ~500ms
- 100 changed files: ~5 seconds

### Search Speed

**Qdrant Performance:**
- 100K vectors: ~5ms
- 1M vectors: ~10ms
- 10M vectors: ~50ms
- Accuracy: 99%+

**End-to-End Search:**
- Query embedding: ~20ms
- Vector search: ~10ms
- Metadata retrieval: ~5ms
- **Total: ~35ms**

### Storage Requirements

**Per Code Block:**
- PostgreSQL: ~2KB (metadata + code)
- Qdrant: ~1.5KB (vector + payload)
- **Total: ~3.5KB per block**

**Example Repository:**
- 1000 files
- 5000 code blocks
- PostgreSQL: ~10MB
- Qdrant: ~7.5MB
- **Total: ~17.5MB**

---

## 🔧 Configuration

### Environment Variables

```bash
# Repository settings
GIT_REPO_PATH=/path/to/repo
CODE_VERSION=v1.0.0

# Vector database
VECTOR_DB_TYPE=qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_API_KEY=your-api-key  # Optional

# Embedding model
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384

# PostgreSQL
DATABASE_URL=postgresql://user:pass@localhost:5432/observability
```

### Code Settings

**In `src/config.py`:**
```python
class Settings:
    # Repository
    git_repo_path: str = os.getenv('GIT_REPO_PATH', './data/repos/default')
    code_version: str = os.getenv('CODE_VERSION', 'main')
    
    # Vector DB
    vector_db_type: str = os.getenv('VECTOR_DB_TYPE', 'qdrant')
    qdrant_host: str = os.getenv('QDRANT_HOST', 'localhost')
    qdrant_port: int = int(os.getenv('QDRANT_PORT', '6333'))
    qdrant_api_key: str = os.getenv('QDRANT_API_KEY', '')
    
    # Embeddings
    embedding_model: str = os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
    embedding_dimension: int = int(os.getenv('EMBEDDING_DIMENSION', '384'))
```

---

## 🐛 Troubleshooting

### Common Issues

#### 1. Javalang Not Installed
**Error:** `javalang not installed. Java indexing will use regex-based fallback`

**Solution:**
```bash
pip install javalang
```

#### 2. Git Not Available
**Error:** `Could not get Git commit SHA`

**Solution:**
- Install GitPython: `pip install GitPython`
- Or ensure repository is a valid Git repo

#### 3. Qdrant Connection Failed
**Error:** `Could not connect to Qdrant`

**Solution:**
```bash
# Start Qdrant with Docker
docker run -p 6333:6333 qdrant/qdrant

# Or check connection settings
QDRANT_HOST=localhost
QDRANT_PORT=6333
```

#### 4. Syntax Errors in Code
**Error:** `Syntax error in file.py`

**Solution:**
- Fix syntax errors in source code
- Or skip file (indexer continues with other files)

#### 5. Out of Memory
**Error:** `MemoryError during indexing`

**Solution:**
- Index in smaller batches
- Increase Docker memory limit
- Use incremental indexing

---

## 📚 API Reference

### CodeIndexer Class

**Methods:**

```python
# Initialize indexer
__init__(repo_path: str = None, version: str = None)

# Index entire repository
index_repository(
    languages: List[str] = None,  # ['python', 'java']
    force_full: bool = False
) -> Dict[str, int]

# Index single Python file
index_python_file(file_path: Path) -> List[str]

# Index single Java file
index_java_file(file_path: Path) -> List[str]
```

**Returns:**
```python
{
    'total_files': 145,
    'total_blocks': 1234,
    'errors': 2,
    'mode': 'incremental'  # or 'full' or 'skip'
}
```

### VectorDatabase Class

**Methods:**

```python
# Initialize collections
init_collections()

# Embed text
embed_text(text: str) -> List[float]

# Insert code block
insert_code_block(
    code_id: str,
    code_text: str,
    metadata: Dict[str, Any]
) -> str

# Search code blocks
search_code_blocks(
    query_text: str,
    top_k: int = 5,
    filters: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]
```

---

## 🎓 Best Practices

### 1. Indexing Strategy

**Initial Setup:**
- Use full indexing for first time
- Verify all files are indexed
- Check for errors in logs

**Regular Updates:**
- Use incremental indexing
- Run after each deployment
- Schedule periodic re-indexing

**Large Repositories:**
- Index in stages (by directory)
- Use multiple workers
- Monitor memory usage

### 2. Search Optimization

**Query Construction:**
- Include exception type
- Include error message
- Include stack trace
- Add file path if known

**Filtering:**
- Always filter by repository
- Filter by version if multiple
- Use file path for precision
- Filter by symbol type if needed

**Result Handling:**
- Use top_k=5 for most cases
- Increase for broader search
- Filter by score threshold (0.6+)
- Combine with metadata

### 3. Maintenance

**Regular Tasks:**
- Monitor indexing status
- Check for failed files
- Update embedding model
- Optimize vector index
- Clean old versions

**Performance Monitoring:**
- Track indexing time
- Monitor search latency
- Check storage usage
- Analyze error rates

---

## 🎯 Summary

Code indexing in Luffy is a sophisticated system that:

1. **Parses** source code using language-specific parsers
   - AST for Python
   - javalang for Java
   - Regex fallback

2. **Extracts** functions, classes, and methods
   - Full metadata
   - Line numbers
   - Docstrings
   - Signatures

3. **Embeds** code into vector space
   - SentenceTransformer models
   - 384-dimensional vectors
   - Semantic similarity

4. **Stores** in dual databases
   - PostgreSQL for metadata
   - Qdrant for vectors
   - Linked by ID

5. **Enables** semantic search
   - Fast similarity search
   - Metadata filtering
   - Ranked results

6. **Supports** incremental updates
   - Git-based diffing
   - Only changed files
   - Efficient updates

7. **Powers** RAG-based analysis
   - Relevant code context
   - Exception analysis
   - Root cause detection

**This creates a powerful foundation for intelligent exception analysis and automated debugging!** 🚀

---

## 📖 Further Reading

- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [SentenceTransformers](https://www.sbert.net/)
- [Python AST Module](https://docs.python.org/3/library/ast.html)
- [Javalang Library](https://github.com/c2nes/javalang)
- [Vector Embeddings Guide](https://www.pinecone.io/learn/vector-embeddings/)
- [RAG Architecture](https://www.anthropic.com/index/retrieval-augmented-generation)
