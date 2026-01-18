#!/bin/bash

# Luffy Observability Platform - One-Command Installation Script
# This script automates the complete installation and setup of Luffy

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Configuration
INSTALL_MODE="${1:-simple}"  # simple, full, or production
SKIP_CHECKS="${SKIP_CHECKS:-false}"

# Functions
print_header() {
    echo ""
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

check_command() {
    if command -v "$1" &> /dev/null; then
        print_success "$1 is installed"
        return 0
    else
        print_error "$1 is not installed"
        return 1
    fi
}

# Main installation function
main() {
    print_header "🚀 Luffy Observability Platform Installer"
    
    echo "Installation Mode: $INSTALL_MODE"
    echo "Project Root: $PROJECT_ROOT"
    echo ""
    
    # Step 1: Check prerequisites
    if [ "$SKIP_CHECKS" != "true" ]; then
        check_prerequisites
    fi
    
    # Step 2: Setup environment
    setup_environment
    
    # Step 3: Start services
    start_services
    
    # Step 4: Initialize database
    initialize_database
    
    # Step 5: Run migrations
    run_migrations
    
    # Step 6: Create default service
    create_default_service
    
    # Step 7: Display access information
    display_access_info
    
    print_header "🎉 Installation Complete!"
}

check_prerequisites() {
    print_header "📋 Checking Prerequisites"
    
    local all_ok=true
    
    # Check Docker
    if check_command docker; then
        DOCKER_VERSION=$(docker --version | awk '{print $3}' | sed 's/,//')
        print_info "Docker version: $DOCKER_VERSION"
    else
        print_error "Docker is required. Install from: https://docs.docker.com/get-docker/"
        all_ok=false
    fi
    
    # Check Docker Compose
    if check_command docker-compose || docker compose version &> /dev/null; then
        if docker compose version &> /dev/null; then
            COMPOSE_VERSION=$(docker compose version | awk '{print $4}')
        else
            COMPOSE_VERSION=$(docker-compose --version | awk '{print $4}' | sed 's/,//')
        fi
        print_info "Docker Compose version: $COMPOSE_VERSION"
    else
        print_error "Docker Compose is required"
        all_ok=false
    fi
    
    # Check available disk space
    AVAILABLE_SPACE=$(df -h "$PROJECT_ROOT" | awk 'NR==2 {print $4}')
    print_info "Available disk space: $AVAILABLE_SPACE"
    
    # Check available memory
    if [[ "$OSTYPE" == "darwin"* ]]; then
        TOTAL_MEM=$(sysctl -n hw.memsize | awk '{print int($1/1024/1024/1024)}')
    else
        TOTAL_MEM=$(free -g | awk 'NR==2 {print $2}')
    fi
    print_info "Total memory: ${TOTAL_MEM}GB"
    
    if [ "$TOTAL_MEM" -lt 8 ]; then
        print_warning "Recommended minimum: 8GB RAM. You have ${TOTAL_MEM}GB"
    fi
    
    if [ "$all_ok" = false ]; then
        print_error "Prerequisites check failed. Please install missing dependencies."
        exit 1
    fi
    
    print_success "All prerequisites met!"
}

setup_environment() {
    print_header "🔧 Setting Up Environment"
    
    cd "$PROJECT_ROOT"
    
    # Check if .env exists
    if [ -f .env ]; then
        print_info ".env file already exists"
        read -p "Do you want to overwrite it? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Keeping existing .env file"
            return
        fi
    fi
    
    # Copy .env.example to .env
    if [ -f .env.example ]; then
        cp .env.example .env
        print_success "Created .env file from .env.example"
    else
        print_error ".env.example not found"
        exit 1
    fi
    
    # Generate random passwords
    POSTGRES_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
    REDIS_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
    
    # Update .env with generated passwords
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$POSTGRES_PASSWORD/" .env
        sed -i '' "s/REDIS_PASSWORD=.*/REDIS_PASSWORD=$REDIS_PASSWORD/" .env
    else
        sed -i "s/POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$POSTGRES_PASSWORD/" .env
        sed -i "s/REDIS_PASSWORD=.*/REDIS_PASSWORD=$REDIS_PASSWORD/" .env
    fi
    
    print_success "Environment configured with secure passwords"
    
    # Prompt for OpenAI API key
    echo ""
    print_info "OpenAI API key is required for RCA generation"
    read -p "Enter your OpenAI API key (or press Enter to skip): " OPENAI_KEY
    
    if [ -n "$OPENAI_KEY" ]; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s/OPENAI_API_KEY=.*/OPENAI_API_KEY=$OPENAI_KEY/" .env
        else
            sed -i "s/OPENAI_API_KEY=.*/OPENAI_API_KEY=$OPENAI_KEY/" .env
        fi
        print_success "OpenAI API key configured"
    else
        print_warning "Skipping OpenAI configuration. RCA generation will not work."
    fi
}

start_services() {
    print_header "🐳 Starting Services"
    
    cd "$PROJECT_ROOT"
    
    case "$INSTALL_MODE" in
        simple)
            print_info "Starting in Simple Mode (Analysis Results Only)"
            if [ -f docker-compose.simple.yml ]; then
                docker-compose -f docker-compose.simple.yml up -d
            else
                print_warning "docker-compose.simple.yml not found, using default"
                docker-compose up -d postgres redis qdrant
            fi
            ;;
        full)
            print_info "Starting in Full Mode (With Log Storage)"
            docker-compose up -d
            ;;
        production)
            print_info "Starting in Production Mode"
            docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
            ;;
        *)
            print_error "Invalid install mode: $INSTALL_MODE"
            exit 1
            ;;
    esac
    
    print_success "Services started"
    
    # Wait for services to be ready
    print_info "Waiting for services to be ready..."
    sleep 10
    
    # Check service health
    check_service_health
}

check_service_health() {
    print_info "Checking service health..."
    
    local max_attempts=30
    local attempt=0
    
    # Check PostgreSQL
    while [ $attempt -lt $max_attempts ]; do
        if docker-compose exec -T postgres pg_isready -U luffy_user &> /dev/null; then
            print_success "PostgreSQL is ready"
            break
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
    
    if [ $attempt -eq $max_attempts ]; then
        print_error "PostgreSQL failed to start"
        exit 1
    fi
    
    # Check Redis
    attempt=0
    while [ $attempt -lt $max_attempts ]; do
        if docker-compose exec -T redis redis-cli ping &> /dev/null; then
            print_success "Redis is ready"
            break
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
    
    if [ $attempt -eq $max_attempts ]; then
        print_error "Redis failed to start"
        exit 1
    fi
    
    # Check Qdrant
    attempt=0
    while [ $attempt -lt $max_attempts ]; do
        if curl -s http://localhost:6333/healthz &> /dev/null; then
            print_success "Qdrant is ready"
            break
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
    
    if [ $attempt -eq $max_attempts ]; then
        print_warning "Qdrant may not be ready, continuing anyway..."
    fi
}

initialize_database() {
    print_header "🗄️  Initializing Database"
    
    cd "$PROJECT_ROOT"
    
    # Check if init_db.py exists
    if [ -f scripts/init_db.py ]; then
        print_info "Running database initialization..."
        
        # Run via Docker if API container is running
        if docker-compose ps | grep -q luffy-api; then
            docker-compose exec -T api python scripts/init_db.py
        else
            # Run locally if venv exists
            if [ -d venv ]; then
                source venv/bin/activate
                python scripts/init_db.py
            else
                print_warning "Cannot initialize database. API container not running and no venv found."
                print_info "You may need to run: make init-db"
                return
            fi
        fi
        
        print_success "Database initialized"
    else
        print_warning "scripts/init_db.py not found, skipping"
    fi
}

run_migrations() {
    print_header "🔄 Running Migrations"
    
    cd "$PROJECT_ROOT"
    
    # Find all migration scripts
    MIGRATION_SCRIPTS=$(find scripts -name "migrate_*.py" 2>/dev/null | sort)
    
    if [ -z "$MIGRATION_SCRIPTS" ]; then
        print_info "No migration scripts found"
        return
    fi
    
    for script in $MIGRATION_SCRIPTS; do
        print_info "Running $(basename "$script")..."
        
        # Run via Docker if API container is running
        if docker-compose ps | grep -q luffy-api; then
            docker-compose exec -T api python "$script" || print_warning "Migration failed: $script"
        else
            # Run locally if venv exists
            if [ -d venv ]; then
                source venv/bin/activate
                python "$script" || print_warning "Migration failed: $script"
            else
                print_warning "Cannot run migrations. API container not running and no venv found."
                break
            fi
        fi
    done
    
    print_success "Migrations completed"
}

create_default_service() {
    print_header "🎯 Creating Default Service"
    
    # Wait for API to be ready
    print_info "Waiting for API to be ready..."
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -s http://localhost:8000/health &> /dev/null; then
            print_success "API is ready"
            break
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
    
    if [ $attempt -eq $max_attempts ]; then
        print_warning "API not responding, skipping default service creation"
        return
    fi
    
    # Create default service
    print_info "Creating default service..."
    
    RESPONSE=$(curl -s -X POST "http://localhost:8000/api/v1/services" \
        -H "Content-Type: application/json" \
        -d '{
            "id": "demo-service",
            "name": "Demo Service",
            "description": "Default demo service for testing",
            "log_processing_enabled": true,
            "log_fetch_interval_minutes": 30,
            "rca_generation_enabled": true,
            "code_indexing_enabled": false
        }' 2>&1)
    
    if echo "$RESPONSE" | grep -q "demo-service\|already exists"; then
        print_success "Default service created (or already exists)"
    else
        print_warning "Could not create default service. You can create it manually via UI."
    fi
}

display_access_info() {
    print_header "🌐 Access Information"
    
    echo ""
    echo -e "${GREEN}🎉 Luffy is now running!${NC}"
    echo ""
    echo "Access URLs:"
    echo -e "  ${BLUE}Frontend:${NC}     http://localhost:3000"
    echo -e "  ${BLUE}API:${NC}          http://localhost:8000"
    echo -e "  ${BLUE}API Docs:${NC}     http://localhost:8000/docs"
    echo -e "  ${BLUE}Qdrant UI:${NC}    http://localhost:6333/dashboard"
    
    if [ "$INSTALL_MODE" = "full" ]; then
        echo -e "  ${BLUE}OpenSearch:${NC}   http://localhost:9200"
    fi
    
    echo ""
    echo "Default Credentials:"
    echo -e "  ${BLUE}PostgreSQL:${NC}   luffy_user / (check .env for password)"
    echo -e "  ${BLUE}OpenSearch:${NC}   admin / admin"
    echo ""
    echo "Next Steps:"
    echo "  1. Open http://localhost:3000 in your browser"
    echo "  2. Create a service via UI or API"
    echo "  3. Configure log sources"
    echo "  4. Add Fluent Bit to your applications (see INSTALLATION_GUIDE.md)"
    echo "  5. Monitor exceptions in the dashboard"
    echo ""
    echo "Useful Commands:"
    echo "  ${BLUE}make logs${NC}          - View all logs"
    echo "  ${BLUE}make ps${NC}            - Show running containers"
    echo "  ${BLUE}make health${NC}        - Check service health"
    echo "  ${BLUE}make down${NC}          - Stop all services"
    echo "  ${BLUE}make clean-all${NC}     - Remove all data and start fresh"
    echo ""
    echo "Documentation:"
    echo "  - Installation Guide: INSTALLATION_GUIDE.md"
    echo "  - Fluent Bit Setup: docs/FLUENT_BIT_SETUP.md"
    echo "  - API Reference: http://localhost:8000/docs"
    echo ""
}

# Cleanup on error
cleanup_on_error() {
    print_error "Installation failed!"
    echo ""
    echo "Troubleshooting:"
    echo "  1. Check logs: make logs"
    echo "  2. Check service status: make ps"
    echo "  3. Try manual installation: see INSTALLATION_GUIDE.md"
    echo "  4. Clean up and retry: make clean-all && ./scripts/install.sh"
    echo ""
}

trap cleanup_on_error ERR

# Parse arguments
show_help() {
    echo "Usage: $0 [MODE]"
    echo ""
    echo "Modes:"
    echo "  simple      - Simple mode (PostgreSQL, Redis, Qdrant only) [default]"
    echo "  full        - Full mode (includes OpenSearch, Fluent Bit)"
    echo "  production  - Production mode (optimized settings)"
    echo ""
    echo "Environment Variables:"
    echo "  SKIP_CHECKS=true  - Skip prerequisite checks"
    echo ""
    echo "Examples:"
    echo "  $0                    # Simple mode"
    echo "  $0 full               # Full mode"
    echo "  SKIP_CHECKS=true $0   # Skip checks"
    echo ""
}

if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    show_help
    exit 0
fi

# Run main installation
main
