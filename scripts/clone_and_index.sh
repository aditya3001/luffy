#!/bin/bash
# Clone a GitHub repository and index it
# Usage: ./scripts/clone_and_index.sh <github-url> <version> [languages]

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check arguments
if [ $# -lt 2 ]; then
    echo -e "${RED}Usage: $0 <github-url> <version> [languages]${NC}"
    echo ""
    echo "Examples:"
    echo "  $0 https://github.com/pallets/flask v3.0.0"
    echo "  $0 https://github.com/spring-projects/spring-boot v3.0.0 java"
    echo "  $0 https://github.com/myorg/myrepo main python,java"
    exit 1
fi

GITHUB_URL=$1
VERSION=$2
LANGUAGES=${3:-python}

# Extract repo name from URL
REPO_NAME=$(basename "$GITHUB_URL" .git)

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Code Indexing Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "Repository: ${GREEN}$GITHUB_URL${NC}"
echo -e "Version:    ${GREEN}$VERSION${NC}"
echo -e "Languages:  ${GREEN}$LANGUAGES${NC}"
echo ""

# Create repos directory if it doesn't exist
REPOS_DIR="./data/repos"
mkdir -p "$REPOS_DIR"

# Check if repo already exists
if [ -d "$REPOS_DIR/$REPO_NAME" ]; then
    echo -e "${YELLOW}⚠️  Repository already exists at $REPOS_DIR/$REPO_NAME${NC}"
    read -p "Do you want to pull latest changes? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}📥 Pulling latest changes...${NC}"
        cd "$REPOS_DIR/$REPO_NAME"
        git pull origin "$VERSION" || git pull
        cd ../..
    fi
else
    echo -e "${BLUE}📥 Cloning repository...${NC}"
    cd "$REPOS_DIR"
    git clone "$GITHUB_URL"
    cd ../..
fi

# Checkout specific version
echo -e "${BLUE}🔀 Checking out version $VERSION...${NC}"
cd "$REPOS_DIR/$REPO_NAME"
git checkout "$VERSION" 2>/dev/null || echo -e "${YELLOW}⚠️  Could not checkout $VERSION, using current branch${NC}"
cd ../..

# Check if services are running
echo ""
echo -e "${BLUE}🔍 Checking if services are running...${NC}"
if ! docker-compose -f docker-compose.simple.yml ps | grep -q "luffy-api"; then
    echo -e "${YELLOW}⚠️  Services not running. Starting them now...${NC}"
    docker-compose -f docker-compose.simple.yml up -d
    echo -e "${BLUE}⏳ Waiting for services to be healthy...${NC}"
    sleep 15
else
    echo -e "${GREEN}✅ Services are running${NC}"
fi

# Index the repository
echo ""
echo -e "${BLUE}📚 Indexing repository...${NC}"
echo -e "${YELLOW}This may take a few minutes depending on repository size...${NC}"
echo ""

docker-compose -f docker-compose.simple.yml exec -T api python scripts/index_code.py \
    --repo "/app/data/repos/$REPO_NAME" \
    --version "$VERSION" \
    --languages "$LANGUAGES"

# Verify indexing
echo ""
echo -e "${BLUE}🔍 Verifying indexing...${NC}"
BLOCK_COUNT=$(docker-compose -f docker-compose.simple.yml exec -T postgres psql -U luffy_user -d observability -t -c "SELECT COUNT(*) FROM code_blocks WHERE repository='$REPO_NAME' AND version='$VERSION';" | tr -d ' ')

if [ "$BLOCK_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✅ Successfully indexed $BLOCK_COUNT code blocks!${NC}"
    echo ""
    echo -e "${BLUE}📊 Summary:${NC}"
    docker-compose -f docker-compose.simple.yml exec -T postgres psql -U luffy_user -d observability -c \
        "SELECT symbol_type, COUNT(*) as count FROM code_blocks WHERE repository='$REPO_NAME' AND version='$VERSION' GROUP BY symbol_type;"
else
    echo -e "${RED}❌ No code blocks were indexed. Check the logs for errors.${NC}"
    echo ""
    echo -e "${YELLOW}View logs with: docker-compose -f docker-compose.simple.yml logs api${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✅ Indexing Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Repository: ${GREEN}$REPO_NAME${NC}"
echo -e "Version:    ${GREEN}$VERSION${NC}"
echo -e "Blocks:     ${GREEN}$BLOCK_COUNT${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo -e "  1. Test code search:"
echo -e "     ${YELLOW}curl -X POST http://localhost:8000/api/v1/code/search -H 'Content-Type: application/json' -d '{\"query\": \"your search\", \"repository\": \"$REPO_NAME\"}'${NC}"
echo ""
echo -e "  2. Send logs for analysis:"
echo -e "     ${YELLOW}curl -X POST http://localhost:8000/api/v1/analyze -H 'Content-Type: application/json' -d @sample_logs.json${NC}"
echo ""
echo -e "  3. View indexed code in database:"
echo -e "     ${YELLOW}make db-shell${NC}"
echo -e "     ${YELLOW}SELECT * FROM code_blocks WHERE repository='$REPO_NAME' LIMIT 10;${NC}"
echo ""
