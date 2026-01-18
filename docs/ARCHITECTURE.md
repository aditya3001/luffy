# System Architecture

## Overview

This document describes the architecture of the AI-Powered Log Observability Platform / Log Monitoring tool, designed to automatically identify root causes of exceptions in production logs using code-aware context and LLM analysis.

## Core Principles

1. **Code-Aware Analysis**: Deep integration with source code versioning and structure
2. **Scalable Processing**: Handle millions of log entries efficiently
3. **AI-Powered Insights**: Use LLMs for intelligent root cause analysis
4. **Actionable Results**: Provide developers with precise, actionable information
5. **Continuous Learning**: Improve accuracy through feedback loops

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          LOG SOURCES                                 │
│  (Elasticsearch, CloudWatch, GCP Logging, Files, Datadog, etc.)     │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      INGESTION LAYER                                 │
│  - Connectors (Batch & Streaming)                                   │
│  - Rate limiting, Authentication                                     │
│  - Raw log storage (S3/GCS)                                         │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    PROCESSING PIPELINE                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │   Parsing    │→ │  Filtering   │→ │  Exception   │              │
│  │ (LogAI-based)│  │ (Log Levels) │  │  Extraction  │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  Feature     │→ │  Clustering  │→ │  Sampling &  │              │
│  │  Enrichment  │  │  (LogAI)     │  │  Dedup       │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  CODE-AWARE CONTEXT SERVICE                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  Code Index  │  │  AST Parser  │  │  Embeddings  │              │
│  │ (Versioned)  │  │  (Symbols)   │  │  (Vectors)   │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   LLM ANALYSIS SERVICE                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  Candidate   │→ │  RAG Engine  │→ │  RCA Output  │              │
│  │  Selection   │  │  (Retrieval) │  │  (JSON)      │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      STORAGE LAYER                                   │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────┐ ┌─────────────┐ │
│  │  Object     │ │  Columnar    │ │  Vector DB   │ │  Relational │ │
│  │  Store      │ │  DB (Logs)   │ │  (Embeddings)│ │  DB (Meta)  │ │
│  │  (S3/GCS)   │ │  (ClickHouse)│ │  (Qdrant)    │ │  (Postgres) │ │
│  └─────────────┘ └──────────────┘ └──────────────┘ └─────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     API & DASHBOARD LAYER                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  REST API    │  │  Dashboard   │  │  Alerting &  │              │
│  │  (FastAPI)   │  │  (React)     │  │  Integration │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Ingestion Layer

**Purpose**: Fetch logs from various sources and store raw data

**Components**:
- **Connectors**: Pluggable adapters for different log sources
  - Elasticsearch/OpenSearch connector
  - AWS CloudWatch connector
  - GCP Logging connector
  - File-based connector (tail/batch)
  - Kafka/Kinesis streaming connector

**Responsibilities**:
- Authenticate with log sources
- Fetch logs for specified time intervals (default: last 24 hours)
- Handle pagination and rate limiting
- Tag logs with metadata (service, environment, version, region)
- Store raw logs in object storage for reprocessing
- Forward to processing pipeline

**Configuration**:
```python
LOG_SOURCES = {
    'elasticsearch': {
        'url': 'https://logs.company.com',
        'index_pattern': 'prod-logs-*',
        'auth': 'api_key'
    },
    'cloudwatch': {
        'region': 'us-east-1',
        'log_groups': ['/aws/lambda/api-*']
    }
}
```

### 2. Processing Pipeline

**Purpose**: Transform raw logs into structured, enriched data ready for analysis

#### 2.1 Parsing & Normalization

**Inspired by LogAI's log parsing**:
- Detect log format (JSON, plain text, custom)
- Apply parsers to extract structured fields
- Template mining for unstructured logs
- Normalize to common schema:

```python
{
    "timestamp": "2025-10-12T13:48:49Z",
    "level": "ERROR",
    "service": "api-gateway",
    "version": "v1.2.3",
    "commit_sha": "abc123",
    "logger": "com.company.Handler",
    "message": "Failed to process request",
    "exception": {
        "type": "NullPointerException",
        "message": "Cannot invoke method on null object",
        "stack_trace": [...]
    },
    "attributes": {...},
    "trace_id": "xyz789",
    "request_id": "req-001"
}
```

#### 2.2 Filtering

**Purpose**: Reduce noise and focus on relevant logs

**Filters**:
- Log level: TRACE, DEBUG, INFO, WARN, ERROR
- Service/environment-based filtering
- Custom query filters

#### 2.3 Exception Extraction

**Purpose**: Identify and structure exception data

**Process**:
1. Detect multi-line stack traces
2. Parse each stack frame:
   ```python
   {
       "file": "src/handlers/user.py",
       "function": "get_user_by_id",
       "line": 145,
       "module": "handlers.user",
       "code_context": "user = database.query(user_id)"
   }
   ```
3. Compute fingerprints:
   - **Static fingerprint**: Hash of (file, function, line) for exact matching
   - **Semantic fingerprint**: Embedding of stack frames + exception message

#### 2.4 Clustering (LogAI-Inspired)

**Purpose**: Group similar exceptions to reduce redundancy

**Methods**:
- Fingerprint-based grouping (exact matches)
- Embedding-based clustering (semantic similarity)
- DBSCAN or K-means for anomaly detection

**Output**: Cluster ID for each exception, representative example per cluster

#### 2.5 Feature Enrichment

**Purpose**: Extract additional context

**Features Extracted**:
- Input parameters from logs (key=value patterns, JSON fields)
- Trace correlation (link related logs via trace_id)
- Temporal patterns (frequency, recency)
- Resource usage metrics if available

### 3. Code-Aware Context Service

**Purpose**: Index source code and map exceptions to exact code locations

#### 3.1 Code Indexing

**Process**:
1. **Clone/pull repository** at specific version (commit SHA, tag)
2. **Parse source files** using language-specific AST parsers:
   - Python: `ast` module
   - Java: JavaParser
   - JavaScript/TypeScript: TypeScript Compiler API
   - Go: `go/parser`

3. **Extract symbols**: Functions, classes, methods with:
   - File path
   - Line range (start, end)
   - Symbol name (fully qualified)
   - Docstrings/comments
   - Function signature

4. **Create embeddings**:
   - Chunk code by function/class
   - Generate embeddings using CodeBERT, OpenAI embeddings, or InstructorXL
   - Store in vector database with metadata

**Data Model**:
```python
{
    "id": "code_block_123",
    "repo": "company/api-service",
    "version": "v1.2.3",
    "commit_sha": "abc123",
    "file_path": "src/handlers/user.py",
    "symbol_name": "handlers.user.get_user_by_id",
    "start_line": 140,
    "end_line": 155,
    "code_snippet": "def get_user_by_id(user_id): ...",
    "embedding_vector": [0.1, 0.2, ...],
    "dependencies": ["database.query", "logger.error"]
}
```

#### 3.2 Version Mapping

**Purpose**: Link deployed services to exact code versions

**Process**:
- Capture version/commit SHA at deployment time
- Store in metadata DB: `(service, environment, deployed_at, version, commit_sha)`
- Match logs to code version using log metadata

### 4. LLM Analysis Service

**Purpose**: Use AI to perform root cause analysis and generate actionable insights

#### 4.1 Candidate Selection

**Process**:
1. Extract top N stack frames from exception (prioritize own code over vendor libraries)
2. Query vector DB for top-K code blocks similar to failing frames
3. Rerank using combined score: path similarity + embedding similarity
4. Select final 3-5 candidate code blocks for LLM context

#### 4.2 RAG Engine (Retrieval-Augmented Generation)

**Prompt Structure**:

**System Prompt**:
```
You are an expert SRE and senior software engineer. Analyze production exceptions 
to identify the root cause code block, involved parameters, and propose fixes.
Output must be valid JSON matching the provided schema.
```

**Context Prompt**:
```
Service: api-gateway
Version: v1.2.3
Commit: abc123

Exception:
Type: NullPointerException
Message: Cannot invoke method on null object
Top Stack Frames:
1. src/handlers/user.py:145 in get_user_by_id
2. src/database/query.py:89 in query
3. src/models/user.py:34 in from_dict

Code Candidates:
1. handlers.user.get_user_by_id (lines 140-155):
   ```python
   def get_user_by_id(user_id):
       user_data = database.query(user_id)
       return User.from_dict(user_data)  # Line 145
   ```

Extracted Parameters:
- user_id: "12345"
- request_path: "/api/users/12345"
```

**User Prompt**:
```
Identify the likely root cause, list involved parameters, and propose fixes.
Return JSON only with fields: likely_root_cause, supporting_evidence, 
involved_parameters, fix_suggestions, tests_to_add.
```

**Output Schema**:
```json
{
    "incident_id": "cluster_001",
    "likely_root_cause": {
        "file_path": "src/handlers/user.py",
        "symbol": "get_user_by_id",
        "line_range": [142, 145],
        "confidence": 0.92,
        "reasoning": "database.query() returned None when user not found"
    },
    "involved_parameters": [
        {
            "name": "user_id",
            "value": "12345",
            "why_relevant": "User ID not found in database"
        }
    ],
    "fix_suggestions": [
        "Add null check after database.query()",
        "Return 404 error when user not found"
    ],
    "tests_to_add": [
        "Test get_user_by_id with non-existent user_id"
    ]
}
```

#### 4.3 Cost & Performance Optimizations

- **Caching**: Cache RCA results per (cluster_id, version)
- **Batching**: Process clusters, not individual exceptions
- **Token management**: Limit context size, summarize repeated info
- **Fallbacks**: Use smaller models for simple cases

### 5. Storage Layer

**Multi-tier storage for different data types**:

#### 5.1 Object Storage (S3/GCS/Azure Blob)
- Raw log archives
- Checkpoints and snapshots
- Prompt/response history

#### 5.2 Columnar Database (ClickHouse/BigQuery)
- Normalized logs (billions of rows)
- Fast aggregations and time-series queries
- Efficient compression

#### 5.3 Vector Database (Qdrant/Weaviate/FAISS)
- Code embeddings
- Log embeddings
- Fast similarity search

#### 5.4 Relational Database (PostgreSQL/MySQL)
- Metadata (services, versions, deployments)
- Exceptions and clusters
- RCA results
- User feedback

**Schema Examples**:

```sql
-- Clusters table
CREATE TABLE clusters (
    cluster_id VARCHAR PRIMARY KEY,
    fingerprint_static VARCHAR,
    fingerprint_semantic BYTEA,
    first_seen TIMESTAMP,
    last_seen TIMESTAMP,
    count_24h INTEGER,
    representative_exception_id VARCHAR,
    status VARCHAR  -- new, investigating, resolved
);

-- RCA results table
CREATE TABLE rca_results (
    rca_id VARCHAR PRIMARY KEY,
    cluster_id VARCHAR REFERENCES clusters(cluster_id),
    version VARCHAR,
    suspected_file VARCHAR,
    suspected_symbol VARCHAR,
    line_range INT[],
    confidence FLOAT,
    parameters JSONB,
    fix_suggestions TEXT[],
    created_at TIMESTAMP
);

-- Feedback table
CREATE TABLE feedback (
    feedback_id VARCHAR PRIMARY KEY,
    rca_id VARCHAR REFERENCES rca_results(rca_id),
    user_id VARCHAR,
    verdict VARCHAR,  -- accept, reject, partially_correct
    notes TEXT,
    created_at TIMESTAMP
);
```

### 6. API & Dashboard Layer

#### 6.1 REST API (FastAPI)

**Key Endpoints**:
- `GET /api/v1/clusters` - List exception clusters with filters
- `GET /api/v1/clusters/{cluster_id}` - Get cluster details
- `GET /api/v1/rca/{cluster_id}` - Get RCA for cluster
- `POST /api/v1/feedback` - Submit feedback on RCA
- `GET /api/v1/search` - Search logs and exceptions
- `GET /api/v1/code/{file_path}` - Get code snippet with highlighting

#### 6.2 Dashboard (React)

**Views**:
1. **Overview Dashboard**:
   - Timeline of exceptions (last 24h, 7d, 30d)
   - Top clusters by frequency
   - Services health status
   - Recent RCA results

2. **Cluster Detail View**:
   - Representative exception
   - Full stack trace with links
   - RCA summary card
   - Code snippet with highlighted lines
   - Parameter spotlight
   - Fix suggestions
   - Similar past incidents

3. **Code Heatmap**:
   - Files ranked by failure frequency
   - Function-level drill-down
   - Version comparison

4. **Search & Filters**:
   - Free-text search
   - Filters: service, environment, level, time range
   - Saved queries

**UI Components**:
- Monaco Editor for code display with syntax highlighting
- ECharts for timelines and distributions
- React Table for cluster lists
- Toast notifications for alerts

## Data Flow

### End-to-End Flow for Exception Analysis

```
1. Log Emission (Production)
   ↓
2. Log Ingestion (Pull/Stream every 5 mins or real-time)
   ↓
3. Parsing & Normalization
   ↓
4. Exception Detection & Frame Extraction
   ↓
5. Clustering (group by fingerprint)
   ↓
6. Representative Selection (1 per cluster)
   ↓
7. Code Context Retrieval (top-K code blocks from vector DB)
   ↓
8. LLM RCA (RAG with logs + code snippets)
   ↓
9. RCA Validation & Storage
   ↓
10. Dashboard Display
   ↓
11. User Feedback Collection
   ↓
12. Feedback Loop (improve prompts/ranking)
```

## Technology Stack

### Backend
- **Python 3.9+**: Main language
- **FastAPI**: REST API framework
- **Celery**: Async task queue
- **Redis**: Caching and message broker
- **Pydantic**: Data validation

### Processing & ML
- **LogAI patterns**: Log parsing and clustering inspiration
- **scikit-learn**: Clustering algorithms
- **sentence-transformers**: Embeddings
- **OpenAI API / Anthropic**: LLM for RCA
- **Tree-sitter** (optional): Advanced code parsing

### Storage
- **PostgreSQL**: Metadata and relational data
- **ClickHouse** or **OpenSearch**: Log storage
- **Qdrant** or **FAISS**: Vector storage
- **S3/GCS**: Object storage

### Frontend
- **React 18**: UI framework
- **TypeScript**: Type safety
- **ECharts**: Visualizations
- **Monaco Editor**: Code display
- **Tailwind CSS**: Styling

### Infrastructure
- **Docker**: Containerization
- **Docker Compose**: Local development
- **Kubernetes** (optional): Production orchestration
- **GitHub Actions**: CI/CD

## Scalability Considerations

### Horizontal Scaling
- **Ingestion**: Multiple workers pulling from different sources
- **Processing**: Partitioned by service/time range
- **LLM Analysis**: Queue-based with rate limiting

### Performance Optimizations
- **Sampling**: Process representative samples, not every log
- **Deduplication**: Cluster and cache results
- **Lazy loading**: Load code context only when needed
- **Incremental indexing**: Update only changed files

### Cost Management
- **LLM calls**: Cluster-first, cache-first strategy
- **Storage tiering**: Hot (recent) vs cold (archived) data
- **Compression**: Use efficient encoding for logs

## Security & Privacy

### Data Security
- **Encryption at rest**: All storage layers
- **Encryption in transit**: TLS for all communications
- **API authentication**: JWT tokens, API keys
- **RBAC**: Role-based access control

### PII Handling
- **Masking**: Redact sensitive parameters before LLM
- **Allowlist**: Only specified fields sent to LLM
- **Audit logs**: Track all data access

## Monitoring & Observability

### System Health Metrics
- Ingestion lag (time between log emission and processing)
- Processing throughput (logs/second)
- LLM latency and error rate
- Storage usage and growth
- API response times

### Quality Metrics
- RCA accuracy (user acceptance rate)
- Coverage (% of clusters with RCA)
- Mean Time to Insight (MTTI)
- False positive rate

## Future Enhancements

- Real-time streaming analysis
- Predictive failure detection
- Auto-remediation suggestions
- Integration with incident management (PagerDuty, Jira)
- Multi-language support expansion
- Federated learning for privacy-preserving improvements
