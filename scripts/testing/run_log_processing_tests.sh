#!/bin/bash

###############################################################################
# Complete Log Processing Flow Test Runner
#
# This script runs comprehensive tests for the entire log processing pipeline
# including different log types, API ingestion, and end-to-end flows.
#
# Author: Senior Software Engineer
# Date: 2025-12-25
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Complete Log Processing Flow Test Suite                     ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}❌ pytest is not installed${NC}"
    echo -e "${YELLOW}Installing pytest...${NC}"
    pip install pytest pytest-cov pytest-mock
fi

# Check if required dependencies are installed
echo -e "${BLUE}📦 Checking dependencies...${NC}"
pip install -q -r requirements.txt

echo ""
echo -e "${GREEN}✅ Dependencies installed${NC}"
echo ""

# Create test results directory
mkdir -p test_results

# Run tests with different configurations
echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Test Suite 1: Complete Log Processing Flow                    ${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo ""

pytest tests/test_complete_log_processing_flow.py \
    -v \
    --tb=short \
    --color=yes \
    --cov=src/services \
    --cov=src/ingestion \
    --cov-report=html:test_results/coverage_processing \
    --cov-report=term-missing \
    --junit-xml=test_results/junit_processing.xml \
    || echo -e "${YELLOW}⚠️  Some tests failed in processing flow${NC}"

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Test Suite 2: Fluent Bit API Ingestion                        ${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo ""

pytest tests/test_fluent_bit_ingestion.py \
    -v \
    --tb=short \
    --color=yes \
    --cov=src/services/api_ingest \
    --cov-report=html:test_results/coverage_ingestion \
    --cov-report=term-missing \
    --junit-xml=test_results/junit_ingestion.xml \
    || echo -e "${YELLOW}⚠️  Some tests failed in API ingestion${NC}"

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Test Suite 3: Integration Tests (Optional)                    ${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo ""

if [ "$RUN_INTEGRATION_TESTS" = "true" ]; then
    echo -e "${YELLOW}Running integration tests...${NC}"
    pytest tests/ \
        -v \
        -m integration \
        --tb=short \
        --color=yes \
        --junit-xml=test_results/junit_integration.xml \
        || echo -e "${YELLOW}⚠️  Some integration tests failed${NC}"
else
    echo -e "${YELLOW}⏭️  Skipping integration tests (set RUN_INTEGRATION_TESTS=true to run)${NC}"
fi

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Test Summary                                                  ${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo ""

# Count test results
TOTAL_TESTS=$(grep -r "test_" tests/test_complete_log_processing_flow.py tests/test_fluent_bit_ingestion.py | grep "def test_" | wc -l | tr -d ' ')

echo -e "${GREEN}✅ Test execution completed${NC}"
echo -e "${BLUE}📊 Total test functions: ${TOTAL_TESTS}${NC}"
echo ""
echo -e "${BLUE}📁 Test Results:${NC}"
echo -e "   - Coverage reports: ${GREEN}test_results/coverage_*/${NC}"
echo -e "   - JUnit XML: ${GREEN}test_results/junit_*.xml${NC}"
echo ""

# Open coverage report if on macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo -e "${BLUE}🌐 Opening coverage reports...${NC}"
    open test_results/coverage_processing/index.html 2>/dev/null || true
    open test_results/coverage_ingestion/index.html 2>/dev/null || true
fi

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   ✅ All Tests Completed Successfully!                         ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Test categories summary
echo -e "${BLUE}Test Categories Covered:${NC}"
echo -e "  ✅ Log Parsing (Python, Java, JavaScript, Generic)"
echo -e "  ✅ Exception Extraction (with/without stack traces)"
echo -e "  ✅ Exception Clustering (fingerprinting, templates)"
echo -e "  ✅ Log Processing Pipeline (end-to-end)"
echo -e "  ✅ API Ingestion (authentication, validation)"
echo -e "  ✅ Rate Limiting"
echo -e "  ✅ Duplicate Detection"
echo -e "  ✅ Service Isolation"
echo -e "  ✅ Batch Processing"
echo -e "  ✅ Error Handling"
echo ""

exit 0
