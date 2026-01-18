# Implementation Guide

## Overview

This document provides a comprehensive guide to the AI-Powered Log Observability Platform implementation. The system analyzes production logs to automatically identify root causes of exceptions using code-aware context and LLM-based analysis.

## Architecture Summary

The platform consists of 6 main components:

1. **Configuration Management** - Centralized settings using Pydantic
2. **Storage Layer** - PostgreSQL for metadata, Qdrant for vectors
3. **Ingestion & Processing** - Log parsing, exception extraction, and clustering
4. **Code Indexer** - AST-based code parsing and embedding generation
5. **LLM Analyzer** - RAG-based root cause analysis
6. **REST API** - FastAPI endpoints for querying and analysis

## Project Structure

```
luffy-demo/
├── .env.example              # Environment configuration template
├── requirements.txt          # Python dependencies
├── data/
│   └── sample.log           # Sample log file for testing
├── docs/
│   ├── ARCHITECTURE.md      # System architecture details
│   ├── SOLUTION_FLOW.md     # Visual flow diagrams
│   ├── API_REFERENCE.md     # API documentation
│   ├── DEPLOYMENT.md        # Deployment guide
│   └── IMPLEMENTATION.md    # This file
├── scripts/
│   ├── index_code.py        # CLI: Index code repository
│   ├── process_logs.py      # CLI: Process log files
│   └── start_api.py         # CLI: Start API server
└── src/
    ├── config/
    │   ├── __init__.py
    │   └── settings.py      # Configuration management
    ├── ingestion/
    │   ├── __init__.py
    │   └── log_parser.py    # Log parsing and normalization
    ├── services/
    │   ├── __init__.py
    │   ├── clustering.py    # Exception clustering
    │   ├── code_indexer.py  # Code repository indexing
    │   ├── exception_extractor.py  # Exception detection
    │   ├── llm_analyzer.py  # LLM-based RCA
    │   ├── processor.py     # Main processing pipeline
    │   └── api.py          # FastAPI REST API
    ├── storage/
    │   ├── __init__.py
    │   ├── database.py      # PostgreSQL connection
    │   ├── models.py        # SQLAlchemy models
    │   └── vector_db.py     # Qdrant vector database
    └── main.py              # Demo entry point
```

## Component Details

### 1. Configuration Management (`src/config/`)

**Purpose**: Centralized configuration using Pydantic Settings with environment variable support.

**Key Files**:
- `settings.py`: Defines all configuration parameters with validation and type checking

**Configuration Categories**:
- Log source settings (Elasticsearch, CloudWatch, files)
- LLM provider configuration (OpenAI, Anthropic)
- Database URLs and connection pools
- Processing parameters (batch size, thresholds)
- Feature flags

**Usage**:
```python
from src.config import settings

print(settings.llm_provider)  # 'openai'
print(settings.log_levels_list)  # ['ERROR', 'CRITICAL']
```

### 2. Storage Layer (`src/storage/`)

#### Database Models (`models.py`)

Defines SQLAlchemy models for:
- **Service**: Application/service metadata
- **ExceptionCluster**: Grouped exceptions with fingerprints
- **RCAResult**: Root cause analysis results
- **Feedback**: User feedback on RCA quality
- **CodeBlock**: Indexed code snippets

#### Database Connection (`database.py`)

Provides:
- SQLAlchemy engine configuration
- Session management with context managers
- Database initialization

**Usage**:
```python
from src.storage.database import get_db, init_db

# Initialize tables
init_db()

# Use database
with get_db() as db:
    clusters = db.query(ExceptionCluster).all()
```

#### Vector Database (`vector_db.py`)

Qdrant client wrapper for:
- Code embedding storage and retrieval
- Log embedding for clustering
- Semantic similarity search

**Key Methods**:
- `embed_text()`: Generate embeddings using sentence-transformers
- `insert_code_block()`: Store code with embedding
- `search_code_blocks()`: RAG retrieval for code context

### 3. Ingestion & Processing

#### Log Parser (`src/ingestion/log_parser.py`)

**Purpose**: Parse structured logs with JSON payloads into normalized format.

**Features**:
- Regex-based pattern matching
- JSON payload extraction
- Timestamp normalization
- Unique log ID generation

**Input Format**:
```
2025-10-13T22:35:12Z ERROR [checkout-service] 192.168.1.10 - TraceId: xyz-123 - Failed to process payment. {"orderId": "ord-98765", "amount": 150.75}
```

**Output**:
```python
{
    'timestamp': '2025-10-13T22:35:12Z',
    'level': 'ERROR',
    'service': 'checkout-service',
    'trace_id': 'xyz-123',
    'message': 'Failed to process payment.',
    'orderId': 'ord-98765',
    'amount': 150.75,
    'log_id': 'abc123...'
}
```

#### Exception Extractor (`src/services/exception_extractor.py`)

**Purpose**: Detect exceptions in logs and extract stack traces.

**Features**:
- Multi-language stack trace parsing (Java, Python)
- Exception type and message extraction
- Static fingerprinting (hash-based)
- Input parameter extraction

**Key Methods**:
- `extract_exception()`: Main extraction logic
- `extract_stack_frames()`: Parse stack trace frames
- `generate_static_fingerprint()`: Create cluster fingerprint
- `extract_input_parameters()`: Get relevant parameters

**Stack Frame Format**:
```python
{
    'symbol': 'com.company.Handler.processPayment',
    'file': 'Handler.java',
    'line': 145,
    'frame_type': 'java'
}
```

#### Exception Clusterer (`src/services/clustering.py`)

**Purpose**: Group similar exceptions using fingerprints and semantic similarity.

**Clustering Strategy**:
1. **Static Fingerprinting**: Hash of exception type + top stack frames
2. **Semantic Similarity**: Vector embeddings for fuzzy matching (future enhancement)

**Features**:
- Automatic cluster creation and updates
- Frequency tracking (24h, 7d)
- RCA trigger logic based on frequency/novelty

**Key Methods**:
- `cluster_exceptions()`: Main clustering logic
- `should_trigger_rca()`: Determine if cluster needs RCA
- `get_cluster_details()`: Retrieve cluster information
- `list_active_clusters()`: Query recent clusters

#### Main Processor (`src/services/processor.py`)

**Purpose**: Orchestrates the complete processing pipeline.

**Pipeline Steps**:
1. Parse logs
2. Filter by log level (ERROR, CRITICAL)
3. Extract exceptions
4. Cluster exceptions
5. Trigger RCA for qualifying clusters

**Usage**:
```python
from src.services.processor import LogProcessor

processor = LogProcessor()
stats = processor.process_log_file('path/to/logs.log')
# Returns: {total_logs, error_logs, exceptions_extracted, clusters_created, rca_generated}
```

### 4. Code Indexer (`src/services/code_indexer.py`)

**Purpose**: Parse code repositories and create searchable embeddings.

**Features**:
- Python AST parsing (extensible to other languages)
- Function and class extraction
- Docstring and signature extraction
- Vector embedding generation
- Storage in both relational DB and vector DB

**Workflow**:
1. Recursively scan repository for source files
2. Parse each file using AST
3. Extract functions/classes with metadata
4. Generate embeddings
5. Store in Qdrant (vectors) and PostgreSQL (metadata)

**Code Block Schema**:
```python
{
    'id': 'code_abc123',
    'repository': 'my-service',
    'version': 'v1.2.3',
    'file_path': 'src/handlers/user.py',
    'symbol_name': 'handlers.user.get_user_by_id',
    'line_start': 140,
    'line_end': 155,
    'code_snippet': 'def get_user_by_id(user_id):\n    ...',
    'docstring': 'Retrieve user by ID',
    'function_signature': 'get_user_by_id(user_id)'
}
```

**Usage**:
```bash
python scripts/index_code.py --repo /path/to/repo --version v1.2.3
```

### 5. LLM Analyzer (`src/services/llm_analyzer.py`)

**Purpose**: Generate root cause analysis using LLM with RAG.

**RAG Architecture**:
1. **Retrieval**: Search vector DB for relevant code blocks based on stack frames
2. **Augmentation**: Build context with exception details + code snippets
3. **Generation**: Call LLM with structured prompt

**Prompt Structure**:
- **System Prompt**: Role definition and JSON schema
- **Context**: Exception details, stack trace, frequency
- **Code Context**: Top-K relevant code blocks from vector search
- **Output Schema**: Structured JSON for parsing

**LLM Response Schema**:
```json
{
  "likely_root_cause": {
    "file_path": "src/handlers/user.py",
    "symbol": "get_user_by_id",
    "line_range": [142, 145],
    "confidence": 0.92,
    "explanation": "NullPointerException due to missing null check..."
  },
  "involved_parameters": [
    {
      "name": "user_id",
      "value": "null",
      "issue": "Parameter is null but method expects valid ID"
    }
  ],
  "fix_suggestions": [
    "Add null check before database query",
    "Return appropriate error response for invalid ID"
  ],
  "tests_to_add": [
    "Test null user_id handling",
    "Test invalid user_id edge cases"
  ]
}
```

**Supported LLM Providers**:
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude)
- Mock mode for testing without API key

### 6. REST API (`src/services/api.py`)

**Purpose**: FastAPI-based REST API for querying and triggering analysis.

**Key Endpoints**:

```
GET  /                          - API info
GET  /health                    - Health check
POST /api/v1/process            - Process a log file
GET  /api/v1/clusters           - List active clusters
GET  /api/v1/clusters/{id}      - Get cluster details
GET  /api/v1/rca/{cluster_id}   - Get RCA result
POST /api/v1/rca/generate       - Trigger RCA generation
POST /api/v1/feedback           - Submit feedback
GET  /api/v1/stats              - System statistics
```

**Interactive Docs**: Visit `http://localhost:8000/docs` for Swagger UI

## Setup Instructions

### 1. Prerequisites

- Python 3.9+
- PostgreSQL (optional for MVP - can mock)
- Qdrant (optional for MVP - can mock)
- OpenAI API key (optional - has mock mode)

### 2. Installation

```bash
# Clone repository
cd /Users/adityajain/Documents/work/ai-project/luffy-demo

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your settings
# Minimal configuration for demo:
LOG_SOURCE=file
LLM_PROVIDER=openai
OPENAI_API_KEY=your-key-here  # Optional - has mock mode
ENABLE_LLM_ANALYSIS=true
```

### 4. Database Setup (Optional)

For full functionality, set up PostgreSQL and Qdrant:

```bash
# PostgreSQL
createdb observability

# Qdrant (using Docker)
docker run -p 6333:6333 qdrant/qdrant

# Initialize database
python -c "from src.storage.database import init_db; init_db()"
```

## Usage Examples

### Demo: Process Sample Logs

```bash
# Run the demo
python src/main.py
```

This will:
1. Parse `data/sample.log`
2. Extract exceptions
3. Create clusters
4. Display detailed analysis
5. (Optional) Generate RCA if LLM is configured

### CLI: Process Custom Log File

```bash
python scripts/process_logs.py --file /path/to/your/logs.log
```

### CLI: Index Your Codebase

```bash
python scripts/index_code.py --repo /path/to/your/service --version v1.2.3
```

### Start API Server

```bash
python scripts/start_api.py
# Or: python -m src.services.api
```

### Query API

```bash
# List clusters
curl http://localhost:8000/api/v1/clusters

# Get cluster details
curl http://localhost:8000/api/v1/clusters/{cluster_id}

# Get RCA
curl http://localhost:8000/api/v1/rca/{cluster_id}

# Trigger RCA generation
curl -X POST http://localhost:8000/api/v1/rca/generate \
  -H "Content-Type: application/json" \
  -d '{"cluster_id": "cluster_abc123"}'
```

## Testing

### Unit Tests (Future)

```bash
pytest tests/
pytest tests/ --cov=src --cov-report=html
```

### Manual Testing Flow

1. **Parse Logs**:
   ```bash
   python src/main.py
   ```

2. **Verify Parsing**: Check console output for parsed logs

3. **Check Clusters**: Verify fingerprinting and clustering

4. **Test API**:
   ```bash
   python scripts/start_api.py
   curl http://localhost:8000/api/v1/clusters
   ```

5. **Test RCA**: If LLM configured, verify RCA generation

## Troubleshooting

### Import Errors

If you encounter import errors:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
```

### Database Connection Issues

Check DATABASE_URL in `.env`:
```bash
# Use SQLite for testing (modify settings.py)
DATABASE_URL=sqlite:///./observability.db
```

### LLM API Errors

If OpenAI API fails:
1. Check API key in `.env`
2. Verify internet connection
3. System falls back to mock mode automatically

### Vector DB Connection Issues

If Qdrant is not running:
1. Start Qdrant: `docker run -p 6333:6333 qdrant/qdrant`
2. Or disable vector search in code (use static fingerprints only)

## Performance Considerations

### For Large Log Volumes

1. **Batch Processing**: Process logs in chunks
2. **Sampling**: Don't analyze every exception, cluster first
3. **Caching**: Cache RCA results for similar clusters
4. **Async Processing**: Use Celery for background tasks

### For Large Codebases

1. **Incremental Indexing**: Only index changed files
2. **Selective Indexing**: Index only relevant directories
3. **Chunking**: Split large files into smaller code blocks

## Next Steps

### MVP Enhancements

1. **Better Error Handling**: More robust exception parsing
2. **More Log Formats**: Support for different log structures
3. **Batch Processing**: CLI for batch log processing
4. **Web Dashboard**: React-based visualization (see docs)

### Production Readiness

1. **Real-time Streaming**: Kafka/Kinesis integration
2. **Distributed Processing**: Celery workers
3. **Monitoring**: Prometheus metrics
4. **Alerting**: Integration with PagerDuty/Slack
5. **Multi-tenancy**: Organization and user management

## Key Design Decisions

1. **Fingerprinting Strategy**: Static (hash) + Semantic (embedding) for flexibility
2. **RAG Approach**: Vector search for code context reduces hallucination
3. **Clustering First**: Reduces LLM calls by grouping similar exceptions
4. **Structured Output**: JSON schema for reliable LLM parsing
5. **Modular Design**: Each component can be replaced/upgraded independently

## References

- [LogAI Paper](https://arxiv.org/abs/2301.13415) - Log analysis inspiration
- [OpenAI Embeddings](https://platform.openai.com/docs/guides/embeddings)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review architecture documentation
3. Check code comments for implementation details
4. Open an issue in the repository
