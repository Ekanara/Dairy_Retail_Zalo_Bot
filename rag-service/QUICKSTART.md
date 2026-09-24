# Quick Start Guide

Get the RAG service running in 5 minutes.

## Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for local development)
- Gemini API key (get from [Google AI Studio](https://makersuite.google.com/app/apikey))

## Step 1: Setup

```bash
cd rag-service

# Copy environment file
make setup

# Edit .env and add your Gemini API key
nano .env  # or vim, code, etc.
```

Update this line in `.env`:
```bash
GEMINI_API_KEY=your_actual_api_key_here
```

## Step 2: Start Services

```bash
# Start all services (Qdrant, TEI Reranker, RAG Service)
make up

# Wait ~30 seconds for TEI reranker to download model
# Check status
make health
```

Expected output:
```json
{
  "status": "healthy",
  "service": "rag-service",
  "qdrant_connected": true,
  "reranker_connected": true
}
```

## Step 3: Test the Service

```bash
# Run the test script
make test
```

This will:
1. Create a test collection
2. Ingest sample documents about Python, FastAPI, vector databases
3. Perform various searches with different configurations
4. Show results with scores and metadata

## Step 4: Use the API

### Create Your Collection

```bash
curl -X POST http://localhost:8006/api/v1/collections \
  -H "Content-Type: application/json" \
  -d '{"project_name": "my_docs"}'
```

### Ingest Your Documents

```bash
curl -X POST http://localhost:8006/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "project_name": "my_docs",
    "chunks": [
      {
        "id": "doc1_chunk1",
        "text": "Your document text here...",
        "metadata": {
          "source": "document.pdf",
          "date": "2024-03-23",
          "lang": "en",
          "chunk_index": 0,
          "total_chunks": 1,
          "extra": {}
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
    "project_name": "my_docs",
    "query": "What is this document about?",
    "top_k": 20,
    "top_n": 5,
    "use_reranker": true,
    "use_mmr": true
  }'
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Health check |
| `/api/v1/collections` | POST | Create collection |
| `/api/v1/collections` | GET | List collections |
| `/api/v1/collections/{name}` | DELETE | Delete collection |
| `/api/v1/ingest` | POST | Ingest documents |
| `/api/v1/search` | POST | Search documents |

## Next Steps

1. **Read the docs**:
   - [README.md](README.md) - Full documentation
   - [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture

2. **Integrate with your app**:
   ```python
   import httpx

   async with httpx.AsyncClient() as client:
       response = await client.post(
           "http://localhost:8006/api/v1/search",
           json={
               "project_name": "my_docs",
               "query": "user question",
               "top_n": 5
           }
       )
       results = response.json()
   ```

3. **Tune performance**:
   - Adjust `top_k` (initial retrieval) and `top_n` (final results)
   - Toggle `use_reranker` and `use_mmr` based on needs
   - Add metadata filters for scoped search

4. **Extend functionality**:
   - Add GraphRAG pipeline
   - Implement image search
   - Add custom metadata fields

## Troubleshooting

### TEI Reranker Not Starting

The reranker downloads a ~1GB model on first start. Check logs:
```bash
make logs-reranker
```

### Gemini API Errors

Check your API key:
```bash
curl -H "x-goog-api-key: YOUR_KEY" \
  "https://generativelanguage.googleapis.com/v1beta/models"
```

### Search Returns No Results

1. Ensure collection exists: `make health`
2. Check ingestion succeeded: `curl http://localhost:8006/api/v1/collections`
3. Verify documents have correct structure

### Connection Refused

Ensure services are running:
```bash
make ps
```

## Stopping Services

```bash
# Stop services (keep data)
make down

# Stop and remove all data
make clean
```

## Support

- Check [README.md](README.md) for detailed documentation
- Review logs: `make logs`
- Open an issue on GitHub
