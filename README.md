# luffy-demo
# AI-Powered Observability for Production Logs

## Project Overview

This project provides an intelligent observability platform that analyzes production logs using AI to automatically identify root causes of exceptions, highlight problematic code blocks, and extract relevant input parameters that triggered failures.

### Key Features

- **Code-Aware Context**: Deep integration with your codebase to map exceptions to exact code locations
- **Intelligent Log Processing**: Advanced filtering, parsing, and clustering of logs (inspired by Salesforce LogAI)
- **AI-Powered RCA**: LLM-based root cause analysis with parameter highlighting
- **Interactive Dashboard**: Visualize incidents, code heatmaps, and actionable insights
- **Feedback Loop**: Continuous improvement through user validation

### Primary Use Case

**Exception Traceback Analysis**: Given a set of exception tracebacks from production logs, the system:
1. Identifies the specific code block causing the exception
2. Highlights the exact lines and symbols involved
3. Extracts and displays the input parameters that triggered the failure
4. Suggests fixes and test cases
5. Presents everything in an intuitive dashboard

## System Architecture

The system consists of 6 main layers:

1. **Log Ingestion Layer**: Fetch logs from various sources (ELK, CloudWatch, files, etc.)
2. **Processing Pipeline**: Parse, normalize, filter, and cluster logs
3. **Code-Aware Context Service**: Index and version codebase with AST and embeddings
4. **LLM Analysis Service**: RAG-based root cause analysis
5. **Storage Layer**: Multi-tier storage for logs, embeddings, and metadata
6. **Dashboard & UI**: Interactive visualization and feedback interface

## Quick Start

### Prerequisites

- Python 3.9+
- Git repository access to your services
- Log source access (Elasticsearch, CloudWatch, or log files)
- OpenAI API key or local LLM setup

### Installation

```bash
# Clone the repository
git clone <your-repo>
cd luffy

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings
```

### Configuration

Edit `.env` file with your settings:

```bash
# Log Source Configuration
LOG_SOURCE=elasticsearch  # elasticsearch, cloudwatch, file
ELASTICSEARCH_URL=http://localhost:9200

# Code Repository
GIT_REPO_PATH=/path/to/your/repo
GIT_BRANCH=main

# LLM Configuration
LLM_PROVIDER=openai  # openai, anthropic, local
OPENAI_API_KEY=your-api-key-here

# Storage
VECTOR_DB=qdrant  # qdrant, faiss, weaviate
DATABASE_URL=postgresql://user:pass@localhost/observability

# Dashboard
DASHBOARD_PORT=3000
API_PORT=8000
```

### Running the System

```bash
# 1. Index your codebase (one-time or on updates)
python -m services.code_indexer --repo /path/to/repo --version v1.2.3

# 2. Start the processing pipeline
python -m services.log_processor

# 3. Start the API server
python -m services.api

# 4. Start the dashboard
cd dashboard
npm install
npm start
```

## Project Structure

```
luffy/
├── docs/
│   ├── ARCHITECTURE.md          # Detailed architecture and design decisions
│   ├── SOLUTION_FLOW.md         # Visual flow diagrams and workflows
│   ├── API_REFERENCE.md         # API endpoints documentation
│   └── DEPLOYMENT.md            # Deployment and scaling guide
├── services/
│   ├── ingestion/               # Log ingestion from various sources
│   ├── processing/              # Log parsing, filtering, clustering
│   ├── code_indexer/            # Code context and embedding creation
│   ├── llm_analyzer/            # LLM-based RCA engine
│   └── api/                     # REST API for dashboard
├── dashboard/                   # React-based UI
├── storage/                     # Storage adapters and models
├── config/                      # Configuration management
├── tests/                       # Unit and integration tests
├── scripts/                     # Utility scripts
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment variables template
└── README.md                    # This file
```

## Documentation

- **[Architecture Guide](docs/ARCHITECTURE.md)**: Detailed system architecture and component descriptions
- **[Solution Flow](docs/SOLUTION_FLOW.md)**: Visual diagrams and data flow
- **[API Reference](docs/API_REFERENCE.md)**: REST API documentation
- **[Deployment Guide](docs/DEPLOYMENT.md)**: Production deployment and scaling

## Technology Stack

- **Backend**: Python (FastAPI, Celery)
- **Processing**: LogAI-inspired patterns, scikit-learn
- **Storage**: PostgreSQL (metadata), ClickHouse/OpenSearch (logs), Qdrant (vectors)
- **LLM**: OpenAI GPT-4 / Anthropic Claude / Local LLMs
- **Frontend**: React, ECharts, Monaco Editor
- **Infrastructure**: Docker, Kubernetes (optional)

## Development Roadmap

### Phase 1: MVP (Weeks 1-4)
- ✅ Core architecture design
- [ ] Basic log ingestion (single source)
- [ ] Exception extraction and parsing
- [ ] Simple code indexing (single repo)
- [ ] Basic LLM RCA with hardcoded prompts
- [ ] Minimal dashboard (cluster list + RCA view)

### Phase 2: Enhanced Features (Weeks 5-8)
- [ ] Multi-source log ingestion
- [ ] Advanced clustering and deduplication
- [ ] Parameter extraction and highlighting
- [ ] Improved prompt engineering
- [ ] Interactive dashboard with code highlighting
- [ ] Feedback mechanism

### Phase 3: Scale & Production (Weeks 9-12)
- [ ] Real-time log streaming
- [ ] Distributed processing
- [ ] Cost optimization (caching, sampling)
- [ ] Alerting and ticket integration
- [ ] Multi-tenancy support
- [ ] Performance monitoring

## Contributing

Contributions are welcome! Please read our contributing guidelines and submit pull requests.

## License

[Your License Here]

## References

- [Salesforce LogAI](https://github.com/salesforce/logai) - Inspiration for log processing and clustering
- [OpenAI API Documentation](https://platform.openai.com/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

## Support

For questions and support, please open an issue or contact the development team.
