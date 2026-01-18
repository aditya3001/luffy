#!/bin/bash
# ===================================
# Docker Build Script with Branch Detection
# ===================================
# Automatically builds Docker images based on Git branch

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() {
    echo -e "${BLUE}$1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

# Auto-detect current branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
BUILD_VERSION=$(git describe --tags --always 2>/dev/null || echo "dev")
BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
GIT_COMMIT=$(git rev-parse HEAD 2>/dev/null || echo "unknown")

# Set environment based on branch
case $CURRENT_BRANCH in
  main|master)
    BUILD_ENV="production"
    IMAGE_TAG="latest"
    ;;
  develop|development)
    BUILD_ENV="development"
    IMAGE_TAG="dev"
    ;;
  staging)
    BUILD_ENV="staging"
    IMAGE_TAG="staging"
    ;;
  *)
    BUILD_ENV="feature"
    IMAGE_TAG="${CURRENT_BRANCH//\//-}"  # Replace / with - in branch name
    ;;
esac

echo "========================================"
echo "Docker Build Configuration"
echo "========================================"
echo "Git Branch:    $CURRENT_BRANCH"
echo "Environment:   $BUILD_ENV"
echo "Version:       $BUILD_VERSION"
echo "Commit:        ${GIT_COMMIT:0:8}"
echo "Build Date:    $BUILD_DATE"
echo "Image Tag:     luffy-platform:$IMAGE_TAG"
echo "========================================"
echo ""

# Build image
print_info "Building Docker image..."

docker build \
  --build-arg GIT_BRANCH=$CURRENT_BRANCH \
  --build-arg BUILD_ENV=$BUILD_ENV \
  --build-arg BUILD_VERSION=$BUILD_VERSION \
  --build-arg BUILD_DATE=$BUILD_DATE \
  --label "git.branch=$CURRENT_BRANCH" \
  --label "git.commit=$GIT_COMMIT" \
  --label "build.date=$BUILD_DATE" \
  --label "build.version=$BUILD_VERSION" \
  -t luffy-platform:$IMAGE_TAG \
  .

print_success "Build complete: luffy-platform:$IMAGE_TAG"
echo ""

# Show image details
print_info "Image Details:"
docker images luffy-platform:$IMAGE_TAG --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"

echo ""
print_info "To test this image, run:"
echo "  ./scripts/test-docker-image.sh luffy-platform:$IMAGE_TAG"
echo ""
print_info "To run this image:"
echo "  docker run -d --env-file .env -p 8000:8000 luffy-platform:$IMAGE_TAG"
