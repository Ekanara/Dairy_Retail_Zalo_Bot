#!/usr/bin/env bash
# Test RAG integration end-to-end

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=========================================="
echo "RAG Integration Test"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Check RAG service is running
echo -e "${YELLOW}[1/6] Checking RAG service...${NC}"
if curl -sf http://localhost:8006/api/v1/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ RAG service is running${NC}"
else
    echo -e "${RED}✗ RAG service is NOT running${NC}"
    echo "  Start with: cd rag-service && docker-compose up -d"
    exit 1
fi

# Test 2: Check Qdrant
echo -e "${YELLOW}[2/6] Checking Qdrant...${NC}"
if curl -sf http://localhost:6333/healthz > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Qdrant is running${NC}"
else
    echo -e "${RED}✗ Qdrant is NOT running${NC}"
    echo "  Start with: cd rag-service && docker-compose up -d qdrant"
    exit 1
fi

# Test 3: Check TEI Reranker
echo -e "${YELLOW}[3/6] Checking TEI Reranker...${NC}"
if curl -sf http://localhost:8005/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ TEI Reranker is running${NC}"
else
    echo -e "${RED}✗ TEI Reranker is NOT running${NC}"
    echo "  Start with: cd rag-service && docker-compose up -d tei-reranker"
    echo "  Note: First start downloads ~1GB model, takes ~30-60s"
    exit 1
fi

# Test 4: Check if products are imported
echo -e "${YELLOW}[4/6] Checking product collection...${NC}"
COLLECTION_CHECK=$(curl -s http://localhost:8006/api/v1/collections | jq -r '.collections[] | select(.name=="magic_sale_products") | .points_count' || echo "0")

if [ "$COLLECTION_CHECK" -gt 0 ]; then
    echo -e "${GREEN}✓ Products imported: $COLLECTION_CHECK chunks${NC}"
else
    echo -e "${RED}✗ No products in RAG${NC}"
    echo "  Import with: cd infrastructure && make import-products"
    echo "  Or: cd rag-service && make import-products"
    exit 1
fi

# Test 5: Test RAG search directly
echo -e "${YELLOW}[5/6] Testing RAG search directly...${NC}"
SEARCH_RESULT=$(curl -s -X POST http://localhost:8006/api/v1/search \
    -H "Content-Type: application/json" \
    -d '{
        "project_name": "magic_sale_products",
        "query": "sữa cho trẻ em biếng ăn",
        "top_k": 20,
        "top_n": 3,
        "use_reranker": true,
        "use_mmr": true
    }' | jq -r '.total_results' || echo "0")

if [ "$SEARCH_RESULT" -gt 0 ]; then
    echo -e "${GREEN}✓ RAG search works: found $SEARCH_RESULT results${NC}"
else
    echo -e "${RED}✗ RAG search returned no results${NC}"
    exit 1
fi

# Test 6: Check MCP service is running
echo -e "${YELLOW}[6/6] Checking MCP service...${NC}"
MCP_STATUS=$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8004/mcp || echo "000")

if [ "$MCP_STATUS" = "200" ] || [ "$MCP_STATUS" = "202" ] || [ "$MCP_STATUS" = "406" ]; then
    echo -e "${GREEN}✓ MCP service is running${NC}"
else
    echo -e "${RED}✗ MCP service is NOT running${NC}"
    echo "  Start with: ./scripts/chat-up.sh"
    exit 1
fi

echo ""
echo "=========================================="
echo -e "${GREEN}All checks passed!${NC}"
echo "=========================================="
echo ""
echo "You can now:"
echo "  1. Test product search: cd rag-service && python scripts/test_product_search.py"
echo "  2. Send message to Zalo bot with complex query"
echo "  3. Check MCP logs: tail -f scripts/logs/mcp-service.log"
echo ""
