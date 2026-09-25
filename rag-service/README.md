# RAG Service

A dynamic, production-ready RAG (Retrieval-Augmented Generation) service implementing the advanced hybrid search pipeline with:

- **Hybrid Search**: Dense (semantic) + Sparse (BM25) vector search
- **RRF Reranking**: Reciprocal Rank Fusion score fusion
- **TEI Reranker**: Neural reranking using Hugging Face Text Embeddings Inference
- **MMR Diversity Filter**: Maximal Marginal Relevance for result diversification
- **Multi-method Architecture**: Designed to easily extend with GraphRAG, image search, etc.

## Architecture

```
User Query → Embed Query (RETRIEVAL_QUERY)
                ↓
         Hybrid Search (dense + sparse + filter)
                ↓
         Re-rank (RRF score fusion + TEI reranker)
                ↓
         MMR Filter (diversity top-5 chunks)
                ↓
         LLM Generation
```

### Ingestion Pipeline

```
Documents → Chunk → Embed (RETRIEVAL_DOCUMENT) → Upsert to Qdrant
                        ↓
            Dense (3072d) + Sparse (BM25)
```

## Features

- **OpenAI-compatible Embedding**: Uses Gemini embedding API with OpenAI SDK for easy model switching
- **Qdrant Vector Database**: Hybrid vector storage with HNSW index for dense vectors and BM25 for sparse
- **TEI Reranker**: High-performance neural reranking with `BAAI/bge-reranker-v2-m3`
- **Async Everything**: Full asyncio support for high performance
- **CRUD Operations**: Complete collection/project management
- **Metadata Filtering**: Filter by source, date, language, custom fields
- **Structured Logging**: JSON logging for production observability

## Installation

### Docker (Recommended)

1. Copy environment variables:
```bash
cp .env.example .env
```

2. Edit `.env` with your Gemini API key:
```bash
GEMINI_API_KEY=your_api_key_here
```

3. Start all services:
```bash
docker-compose up -d
```

Services will be available at:
- RAG API: http://localhost:8006
- Qdrant: http://localhost:6333
- TEI Reranker: http://localhost:8005

### Local Development

1. Create virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Start Qdrant and TEI separately:
```bash
docker-compose up -d qdrant tei-reranker
```

4. Run the service:
```bash
uvicorn main:app --reload --port 8006
```

## API Usage

### Health Check

```bash
curl http://localhost:8006/api/v1/health
```

### Create Collection

```bash
curl -X POST http://localhost:8006/api/v1/collections \
  -H "Content-Type: application/json" \
  -d '{"project_name": "my_project"}'
```

### Ingest Documents

```bash
curl -X POST http://localhost:8006/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "project_name": "my_project",
    "chunks": [
      {
        "id": "doc1_chunk1",
        "text": "Python is a high-level programming language.",
        "metadata": {
          "source": "doc1.pdf",
          "date": "2024-01-15",
          "lang": "en",
          "chunk_index": 0,
          "total_chunks": 3,
          "extra": {"page": 1}
        }
      }
    ]
  }'
```

### Search

```bash
curl -X POST http://localhost:8006/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "project_name": "my_project",
    "query": "What is Python?",
    "top_k": 20,
    "top_n": 5,
    "use_reranker": true,
    "use_mmr": true,
    "filters": {
      "lang": "en"
    }
  }'
```

### List Collections

```bash
curl http://localhost:8006/api/v1/collections
```

### Delete Collection

```bash
curl -X DELETE http://localhost:8006/api/v1/collections/my_project
```

## Configuration

Key environment variables in `.env`:

```bash
# Gemini Embedding (OpenAI-compatible)
GEMINI_API_KEY=your_api_key
GEMINI_API_EMBEDDING_URL=https://generativelanguage.googleapis.com/v1beta
EMBEDDING_MODEL_NAME=models/text-embedding-004

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333

# TEI Reranker
TEI_RERANKER_URL=http://localhost:8005
RERANKER_MODEL_NAME=BAAI/bge-reranker-v2-m3

# RAG Parameters
DEFAULT_TOP_K=20  # Results before reranking
DEFAULT_TOP_N=5   # Final results after MMR
RRF_K=60          # RRF constant
MMR_LAMBDA=0.7    # MMR relevance vs diversity (0-1)
```

## Extending with New Methods

The service is designed to easily add new RAG methods:

### Adding GraphRAG

1. Create `app/services/graph_rag_service.py`
2. Implement graph construction and traversal
3. Add routes in `app/api/routes.py`
4. Update `app/services/rag_service.py` to orchestrate

### Adding Image Search

1. Create `app/services/image_embedding_service.py` (e.g., CLIP)
2. Update Qdrant schema to support image vectors
3. Add image ingestion pipeline
4. Add multimodal search endpoint

## Project Structure

```
rag-service/
├── app/
│   ├── api/              # FastAPI routes
│   │   └── routes.py
│   ├── core/             # Configuration and logging
│   │   ├── config.py
│   │   └── logger.py
│   ├── models/           # Pydantic schemas
│   │   └── schemas.py
│   ├── repositories/     # Data access layer
│   │   └── qdrant_repository.py
│   └── services/         # Business logic
│       ├── embedding_service.py
│       ├── sparse_embedding_service.py
│       ├── reranker_service.py
│       ├── mmr_service.py
│       └── rag_service.py
├── main.py               # Entrypoint
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

## Performance Tuning

### Qdrant HNSW Parameters

Edit collection creation in `qdrant_repository.py`:

```python
vectors_config={
    "dense": VectorParams(
        size=768,
        distance=Distance.COSINE,
        hnsw_config=HnswConfigDiff(
            m=16,              # Bi-directional link count (↑ = better recall, more memory)
            ef_construct=100,  # Construction time parameter (↑ = better quality)
        )
    )
}
```

### Search Parameters

Tune in search request:

- `top_k`: Higher = better recall, slower (default 20)
- `top_n`: Final result count after MMR (default 5)
- `use_reranker`: Significantly improves relevance, adds ~100-200ms
- `use_mmr`: Improves diversity, minimal overhead

### Reranker Model

Change in `.env`:

```bash
# Faster but less accurate
RERANKER_MODEL_NAME=cross-encoder/ms-marco-MiniLM-L-6-v2

# Slower but more accurate (default)
RERANKER_MODEL_NAME=BAAI/bge-reranker-v2-m3
```

## Monitoring

The service uses structured JSON logging. Integrate with your logging stack:

```bash
# View logs
docker-compose logs -f rag-service

# Search logs
docker-compose logs rag-service | jq 'select(.levelname == "ERROR")'
```

## Product Catalog Integration

The service includes built-in support for importing and searching products from data-service.

### Import Products

```bash
# Import all products from data-service
make import-products

# Or manually:
python scripts/import_products_from_data_service.py \
  --data-service-url http://localhost:8002
```

### Search Products

```bash
# Interactive search
make search-products

# Or directly:
python scripts/test_product_search.py --query "sữa cho trẻ em"
```

### Product Transformation

Each product is automatically transformed into 1-3 searchable chunks:
- **Main info**: Name, brand, origin, price, customer segment, age
- **Purpose**: Product benefits and use cases
- **Usage**: How to use instructions

All text is optimized for Vietnamese e-commerce search.

See [PRODUCT_IMPORT_GUIDE.md](PRODUCT_IMPORT_GUIDE.md) for detailed documentation.

## Contributing

Follow the project's coding conventions:

- Async everywhere
- Type hints on all functions
- Structured logging via `app.core.logger`
- snake_case naming
- Conventional Commits (feat:, fix:, chore:)

## Support

For issues, feature requests, or questions, please open an issue on GitHub.
