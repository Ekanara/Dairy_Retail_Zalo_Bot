## Product Import Guide

This guide explains how to import product data from data-service into RAG service for semantic product search.

## Overview

The product import pipeline:
1. **Fetch** products from data-service API
2. **Transform** each product into 1-3 text chunks optimized for Vietnamese search
3. **Ingest** chunks into RAG with embeddings

## Product Transformation

Each product is split into searchable chunks:

### Chunk 1: Main Product Info
```
Sản phẩm: [Product Name]
Thương hiệu: [Brand]
Xuất xứ: [Origin]
Giá: [Price]
Đối tượng: [Customer Segment]
Độ tuổi: [Age Range]
```

### Chunk 2: Product Purpose (if available)
```
Công dụng của [Product Name]:
[Product Purpose text]
```

### Chunk 3: Usage Instructions (if available)
```
Cách sử dụng [Product Name]:
[How to Use text]
```

## Quick Start

### Prerequisites

1. **Data service running** with products loaded:
   ```bash
   cd data-service
   # Ensure database is populated with products
   ```

2. **RAG service running**:
   ```bash
   cd rag-service
   make up
   make health  # Verify all services are healthy
   ```

### Import Products

```bash
cd rag-service

# Import all products from data-service
python scripts/import_products_from_data_service.py \
  --data-service-url http://localhost:8002 \
  --rag-service-url http://localhost:8006 \
  --project-name magic_sale_products \
  --batch-size 10
```

### Test Product Search

```bash
# Single query
python scripts/test_product_search.py --query "sữa cho trẻ em"

# Run test suite with multiple queries
python scripts/test_product_search.py
```

## Import Options

| Option | Default | Description |
|--------|---------|-------------|
| `--data-service-url` | `http://localhost:8002` | Data service API URL |
| `--rag-service-url` | `http://localhost:8006` | RAG service API URL |
| `--project-name` | `magic_sale_products` | RAG collection name |
| `--batch-size` | `10` | Products per ingestion batch |

## Search Options

| Option | Default | Description |
|--------|---------|-------------|
| `--query` | None | Search query (Vietnamese) |
| `--rag-service-url` | `http://localhost:8006` | RAG service API URL |
| `--project-name` | `magic_sale_products` | RAG collection name |
| `--top-n` | `5` | Number of results to return |

## Example Searches

### Vietnamese Product Queries

```bash
# Milk products for children
python scripts/test_product_search.py --query "sữa cho trẻ em"

# Vitamins for elderly
python scripts/test_product_search.py --query "vitamin cho người cao tuổi"

# Diabetes supplements
python scripts/test_product_search.py --query "thuốc tiểu đường"

# Products for pregnant women
python scripts/test_product_search.py --query "sản phẩm cho mẹ bầu"

# Women's health supplements
python scripts/test_product_search.py --query "thực phẩm chức năng cho phụ nữ"
```

### Advanced Filtering

You can filter by metadata programmatically:

```python
import httpx

async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:8006/api/v1/search",
        json={
            "project_name": "magic_sale_products",
            "query": "vitamin",
            "top_n": 5,
            "filters": {
                "customer_segment": "elderly",
                "origin": "usa"
            }
        }
    )
```

## Product Metadata

Each chunk includes structured metadata for filtering and display:

```json
{
  "source": "product_catalog",
  "product_id": "uuid",
  "product_name": "Product Name",
  "brand_name": "Brand Name",
  "chunk_type": "main_info|purpose|usage",
  "origin": "usa|ireland|singapore|vietnam|netherlands",
  "customer_segment": "children|elderly|women|...",
  "customer_age": "age_0m_6m|age_18y_40y|...",
  "price": 100000.0,
  "stock_quantity": 50,
  "lang": "vi"
}
```

## Integration with Models Service

To use RAG search in your chatbot:

```python
import httpx

async def search_products(query: str, top_n: int = 5):
    """Search products using RAG service."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8006/api/v1/search",
            json={
                "project_name": "magic_sale_products",
                "query": query,
                "top_k": 20,
                "top_n": top_n,
                "use_reranker": True,
                "use_mmr": True
            }
        )
        return response.json()

# In your chatbot flow:
results = await search_products("sữa cho trẻ em", top_n=3)

# Format results for LLM context
product_context = "\n\n".join([
    f"{r['metadata']['product_name']}: {r['text']}"
    for r in results['results']
])

# Pass to LLM
prompt = f"""
Dựa trên thông tin sản phẩm sau:
{product_context}

Hỏi của khách hàng: {user_query}

Hãy giới thiệu sản phẩm phù hợp:
"""
```

## Performance Tuning

### Batch Size

- **Small (5-10)**: Faster feedback, more API calls
- **Medium (20-50)**: Balanced
- **Large (100+)**: Fewer API calls, higher memory usage

### Search Parameters

```python
{
  "top_k": 20,      # Initial retrieval (↑ = better recall, slower)
  "top_n": 5,       # Final results (after reranking + MMR)
  "use_reranker": True,   # Neural reranking (+100ms, better quality)
  "use_mmr": True         # Diversity filter (+5ms, diverse results)
}
```

### Re-importing Products

To update product data:

```bash
# Delete existing collection
curl -X DELETE http://localhost:8006/api/v1/collections/magic_sale_products

# Re-import
python scripts/import_products_from_data_service.py
```

## Troubleshooting

### Import Fails: "Collection already exists"

This is OK - the script will use the existing collection. To start fresh:
```bash
curl -X DELETE http://localhost:8006/api/v1/collections/magic_sale_products
```

### Search Returns No Results

1. Check collection exists:
   ```bash
   curl http://localhost:8006/api/v1/collections
   ```

2. Verify data was imported:
   ```bash
   # Should show points_count > 0
   curl http://localhost:8006/api/v1/collections | jq '.collections[] | select(.name=="magic_sale_products")'
   ```

3. Check Gemini API key is set:
   ```bash
   # In rag-service/.env
   grep GEMINI_API_KEY .env
   ```

### Slow Search Performance

1. Ensure TEI reranker is running:
   ```bash
   curl http://localhost:8005/health
   ```

2. Disable reranker for faster (but lower quality) search:
   ```python
   {"use_reranker": False, "use_mmr": False}
   ```

## Example Output

```
🔍 Searching for: 'sữa cho trẻ em'

✅ Found 5 results:

================================================================================

1. [0.8534] Sữa Ensure Gold HMB Vani 850g
   Brand: Abbott
   Type: main_info
   Price: 545,000đ
   Segment: children
   Age: age_4y_12y
   Origin: usa
   Stock: ✓ In stock (50 units)

   Sản phẩm: Sữa Ensure Gold HMB Vani 850g
   Thương hiệu: Abbott
   Xuất xứ: Mỹ
   Giá: 545,000đ
   Đối tượng: Trẻ em
   Độ tuổi: 4-12 tuổi...

2. [0.8201] Sữa Enfamil A+ 1 900g
   Brand: Mead Johnson
   Type: main_info
   Price: 425,000đ
   ...
```

## Next Steps

1. **Integrate with MCP service**: Add `search_products_rag` tool
2. **Update prompts**: Use RAG results in agent context
3. **Add filters**: Implement price range, brand filtering
4. **Monitor quality**: Track search relevance metrics
