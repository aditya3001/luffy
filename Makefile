.PHONY: help build up down restart logs ps clean test

# Default target
help:
	@echo "Available commands:"
	@echo ""
	@echo "🎯 SIMPLE MODE (Analysis Results Only - Recommended for Starter):"
	@echo "  make simple-up      - Start simple mode (PostgreSQL + Redis + Qdrant only)"
	@echo "  make simple-down    - Stop simple mode"
	@echo "  make simple-status  - Check simple mode services"
	@echo ""
	@echo "🏢 FULL MODE (With Log Storage):"
	@echo "  make build          - Build Docker images"
	@echo "  make up             - Start all services (Full mode)"
	@echo "  make up-dev         - Start all services in development mode"
	@echo "  make down           - Stop all services"
	@echo ""
	@echo "🔧 COMMON COMMANDS:"
	@echo "  make restart        - Restart all services"
	@echo "  make logs           - View logs (all services)"
	@echo "  make logs-api       - View API logs"
	@echo "  make logs-worker    - View Celery worker logs"
	@echo "  make ps             - Show running containers"
	@echo "  make shell          - Open shell in API container"
	@echo "  make db-shell       - Open PostgreSQL shell"
	@echo ""
	@echo "📊 DATABASE:"
	@echo "  make migrate        - Run database migrations"
	@echo "  make init-db        - Initialize database schema"
	@echo "  make backup-db      - Backup database"
	@echo ""
	@echo "🧹 CLEANUP:"
	@echo "  make clean          - Stop services and remove containers"
	@echo "  make clean-all      - Stop services and remove containers + volumes"
	@echo ""
	@echo "🧪 DEVELOPMENT:"
	@echo "  make index-code     - Index codebase"
	@echo "  make process-logs   - Process logs"
	@echo "  make test           - Run tests"
	@echo "  make health         - Check API health"

# ============================================
# SIMPLE MODE - Analysis Results Only
# ============================================

# Start simple mode (no log storage)
simple-up:
	docker-compose -f docker-compose.simple.yml up -d
	@echo "✅ Simple mode started (Analysis Results Only)"
	@echo "📖 API docs: http://localhost:8000/docs"
	@echo "📊 Qdrant UI: http://localhost:6333/dashboard"
	@echo ""
	@echo "Services running:"
	@echo "  - PostgreSQL (metadata & analysis results)"
	@echo "  - Redis (cache & task queue)"
	@echo "  - Qdrant (vector embeddings)"
	@echo "  - FastAPI (API server)"
	@echo "  - Celery (async workers)"
	@echo ""
	@echo "💡 To initialize database: make init-db"

# Stop simple mode
simple-down:
	docker-compose -f docker-compose.simple.yml down
	@echo "✅ Simple mode stopped"

# Simple mode with logs
simple-logs:
	docker-compose -f docker-compose.simple.yml logs -f

# Simple mode status
simple-status:
	@echo "=== Simple Mode Service Status ==="
	@docker-compose -f docker-compose.simple.yml ps
	@echo ""
	@echo "=== Health Checks ==="
	@curl -s http://localhost:8000/health | python -m json.tool || echo "❌ API not responding"
	@curl -s http://localhost:6333/healthz && echo "✅ Qdrant OK" || echo "❌ Qdrant not responding"
	@docker-compose -f docker-compose.simple.yml exec postgres pg_isready -U luffy_user && echo "✅ PostgreSQL OK" || echo "❌ PostgreSQL not responding"
	@docker-compose -f docker-compose.simple.yml exec redis redis-cli ping && echo "✅ Redis OK" || echo "❌ Redis not responding"

# Clean simple mode with volumes
simple-clean-all:
	docker-compose -f docker-compose.simple.yml down -v
	@echo "⚠️  Simple mode stopped, containers and volumes removed"

# ============================================
# FULL MODE - With Log Storage
# ============================================

# Build Docker images
build:
	docker-compose build

# Start all services
up:
	docker-compose up -d
	@echo "✅ Services started. API available at http://localhost:8000"
	@echo "📖 API docs: http://localhost:8000/docs"
	@echo "🔍 OpenSearch Dashboards: http://localhost:5601"

# Start in development mode
up-dev:
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
	@echo "✅ Development mode started with hot-reload enabled"

# Stop all services
down:
	docker-compose down

# Restart all services
restart:
	docker-compose restart

# Restart specific service
restart-api:
	docker-compose restart api

restart-worker:
	docker-compose restart celery-worker

# View logs
logs:
	docker-compose logs -f

logs-api:
	docker-compose logs -f api

logs-worker:
	docker-compose logs -f celery-worker

logs-db:
	docker-compose logs -f postgres

# Show running containers
ps:
	docker-compose ps

# Open shell in API container
shell:
	docker-compose exec api bash

# Open PostgreSQL shell
db-shell:
	docker-compose exec postgres psql -U luffy_user -d observability

# Database migrations
migrate:
	docker-compose exec api alembic upgrade head

migrate-create:
	@read -p "Enter migration message: " msg; \
	docker-compose exec api alembic revision --autogenerate -m "$$msg"

# Initialize database schema (works with both modes)
init-db:
	@echo "Initializing database schema..."
	@if [ -f docker-compose.simple.yml ] && docker-compose -f docker-compose.simple.yml ps | grep -q luffy-api; then \
		docker-compose -f docker-compose.simple.yml exec api python scripts/init_db.py; \
	else \
		docker-compose exec api python scripts/init_db.py; \
	fi
	@echo "✅ Database initialized"

# Index codebase
index-code:
	@read -p "Enter repo path (e.g., /app/data/repo): " repo; \
	read -p "Enter version (e.g., v1.0.0): " version; \
	docker-compose exec api python scripts/index_code.py --repo $$repo --version $$version

# Process logs
process-logs:
	docker-compose exec api python scripts/process_logs.py

# Run full pipeline
run-pipeline:
	docker-compose exec api python scripts/run_pipeline.py

# Clean up
clean:
	docker-compose down
	@echo "✅ Services stopped and containers removed"

clean-all:
	docker-compose down -v
	@echo "⚠️  Services stopped, containers and volumes removed"

# Run tests
test:
	docker-compose exec api pytest tests/ -v

test-coverage:
	docker-compose exec api pytest tests/ --cov=src --cov-report=html

# Health check
health:
	@curl -f http://localhost:8000/health && echo "\n✅ API is healthy" || echo "\n❌ API is not responding"

# Check service status
status:
	@echo "=== Service Status ==="
	@docker-compose ps
	@echo "\n=== Health Checks ==="
	@curl -s http://localhost:8000/health | python -m json.tool || echo "❌ API not responding"
	@curl -s http://localhost:6333/healthz && echo "✅ Qdrant OK" || echo "❌ Qdrant not responding"
	@curl -s http://localhost:9200/_cluster/health | python -m json.tool || echo "❌ OpenSearch not responding"

# View resource usage
stats:
	docker stats --no-stream

# Backup database
backup-db:
	@echo "Creating database backup..."
	@docker-compose exec -T postgres pg_dump -U luffy_user observability > backup_$$(date +%Y%m%d_%H%M%S).sql
	@echo "✅ Backup created: backup_$$(date +%Y%m%d_%H%M%S).sql"

# Restore database
restore-db:
	@read -p "Enter backup file path: " file; \
	cat $$file | docker-compose exec -T postgres psql -U luffy_user observability
	@echo "✅ Database restored"
