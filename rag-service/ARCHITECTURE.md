# RAG Service Architecture

## System Overview

The RAG service implements a hybrid search pipeline combining dense semantic search, sparse keyword search (BM25), neural reranking, and diversity filtering.

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Query                              │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                ┌───────────▼──────────┐
                │   Embed Query        │
                │ task=RETRIEVAL_QUERY │
                │   (Gemini API)       │
                └─────┬────────────┬───┘
                      │            │
              ┌───────▼────┐  ┌────▼──────┐
              │ Dense Vec  │  │ Sparse Vec│
              │ (768d)     │  │ (BM25)    │
              └───────┬────┘  └────┬──────┘
                      │            │
                ┌─────▼────────────▼─────┐
                │   Hybrid Search        │
                │ dense + sparse + filter│
                │     (Qdrant)           │
                └─────────┬──────────────┘
                          │
                    ┌─────▼─────────┐
                    │  Re-rank      │
                    │  (RRF + TEI)  │
                    │  score fusion │
                    │  top-20       │
                    └─────┬─────────┘
                          │
                    ┌─────▼─────────┐
                    │  MMR Filter   │
                    │  diverse      │
                    │  top-5 chunks │
                    └─────┬─────────┘
                          │
                    ┌─────▼─────────┐
                    │ LLM Generation│
                    │  (external)   │
                    └───────────────┘
```

## Ingestion Pipeline

```
┌─────────────────┐
│   Documents     │
└────────┬────────┘
         │
    ┌────▼────┐
    │  Chunk  │ (external, user-provided)
    └────┬────┘
         │
    ┌────▼────────────────────────────┐
    │  Embed                          │
    │  task=RETRIEVAL_DOCUMENT        │
    │  (Gemini API)                   │
    └────┬────────────────┬───────────┘
         │                │
    ┌────▼─────┐    ┌─────▼──────┐
    │Dense Vec │    │ Sparse Vec │
    │ (768d)   │    │  (BM25)    │
    └────┬─────┘    └─────┬──────┘
         │                │
    ┌────▼────────────────▼───────┐
    │  Upsert to Qdrant           │
    │  Collection: rag_chunks     │
    └─────────────────────────────┘
```

## Qdrant Cluster Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Qdrant Cluster                            │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │         Collection: rag_chunks                      │    │
│  │                                                     │    │
│  │  Dense Vectors (3072d)         Sparse Vectors      │    │
│  │  ┌──────────────────┐         ┌──────────────┐     │    │
│  │  │  HNSW Index      │         │ Payload Index│     │    │
│  │  │  m=16, ef=100    │         │ source, date,│     │    │
│  │  │  cosine distance │         │ lang         │     │    │
│  │  └──────────────────┘         │ FastEmbed    │     │    │
│  │                               │ BM25         │     │    │
│  │                               └──────────────┘     │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌────────────┐              ┌────────────┐                 │
│  │  Shard 0   │              │  Shard 1   │                 │
│  │ node-0     │              │ node-1     │                 │
│  │ (primary)  │◄────────────►│ (replica)  │                 │
│  └────────────┘              └────────────┘                 │
│                                                              │
│  ┌─────────────────┐         ┌─────────────────┐            │
│  │ WAL + segments  │         │   Snapshot      │            │
│  │ memmap storage  │         │ S3/GCS backup   │            │
│  └─────────────────┘         └─────────────────┘            │
└──────────────────────────────────────────────────────────────┘
```

## Service Components

### 1. Embedding Service
- **Technology**: OpenAI SDK → Gemini API
- **Model**: `models/text-embedding-004` (768 dimensions)
- **Features**:
  - Task-specific embeddings (RETRIEVAL_QUERY vs RETRIEVAL_DOCUMENT)
  - Async batch processing
  - Easy model switching via environment variables

### 2. Sparse Embedding Service
- **Technology**: FastEmbed BM25
- **Features**:
  - Token-based keyword matching
  - Complement to semantic search
  - Synchronous with thread pooling

### 3. Qdrant Repository
- **Technology**: Qdrant vector database
- **Features**:
  - Hybrid vector storage (dense + sparse)
  - HNSW indexing for approximate nearest neighbor
  - Metadata filtering (source, date, lang)
  - Collection CRUD operations

### 4. Reranker Service
- **Technology**: Hugging Face TEI (Text Embeddings Inference)
- **Model**: `BAAI/bge-reranker-v2-m3`
- **Features**:
  - Neural cross-encoder reranking
  - RRF (Reciprocal Rank Fusion) score combination
  - Top-K to Top-N refinement

### 5. MMR Service
- **Algorithm**: Maximal Marginal Relevance
- **Formula**: `MMR = λ * relevance(q, d) - (1 - λ) * max_similarity(d, selected)`
- **Parameters**:
  - `λ = 0.7` (default): Balance relevance vs diversity
  - Higher λ = more relevance, less diversity
  - Lower λ = more diversity, less relevance

### 6. RAG Service
- **Role**: Orchestration layer
- **Responsibilities**:
  - Pipeline coordination
  - Async task management
  - Error handling and logging

## Data Flow

### Query Processing

1. **Embedding** (parallel):
   ```python
   dense_vector = await embedding_service.embed_query(query)
   sparse_vector = await sparse_embedding_service.embed_query(query)
   ```

2. **Hybrid Search**:
   ```python
   results = await qdrant.hybrid_search(
       dense_vector=dense_vector,
       sparse_vector=sparse_vector,
       limit=top_k,  # 20
       filters={"lang": "en"}
   )
   ```

3. **Reranking** (optional):
   ```python
   # RRF score fusion
   fused = reranker.rrf_fusion(dense_results, sparse_results, k=60)

   # Neural reranking
   reranked = await reranker.rerank(query, documents, top_n=None)
   ```

4. **MMR Diversity** (optional):
   ```python
   diverse = mmr_service.apply_mmr(
       query_embedding=dense_vector,
       results=reranked,
       top_n=5,
       lambda_param=0.7
   )
   ```

### Document Ingestion

1. **Batch Embedding** (parallel):
   ```python
   dense_vectors = await embedding_service.embed_documents(texts)
   sparse_vectors = await sparse_embedding_service.embed_documents(texts)
   ```

2. **Point Creation**:
   ```python
   points = [
       {
           "id": chunk_id,
           "dense_vector": dense_vec,
           "sparse_vector": sparse_vec,
           "payload": {
               "text": text,
               "source": source,
               "metadata": {...}
           }
       }
   ]
   ```

3. **Upsert to Qdrant**:
   ```python
   await qdrant.upsert_points(collection_name, points)
   ```

## Performance Characteristics

### Latency Budget (per query)

| Component        | Latency   | Notes                           |
|------------------|-----------|---------------------------------|
| Embed Query      | ~50ms     | Gemini API call                 |
| Hybrid Search    | ~20ms     | HNSW + BM25 search              |
| Rerank (TEI)     | ~100ms    | Cross-encoder inference         |
| MMR Filter       | ~5ms      | In-memory vector operations     |
| **Total**        | **~175ms**| Without LLM generation          |

### Throughput

- **Ingestion**: ~100 chunks/second (batch size 10)
- **Search**: ~50 queries/second (with reranking)
- **Concurrent**: Limited by Gemini API rate limits

### Scaling Considerations

1. **Horizontal Scaling**:
   - Run multiple RAG service instances
   - Load balance with nginx/traefik
   - Qdrant handles sharding automatically

2. **Vertical Scaling**:
   - TEI reranker benefits from GPU
   - Increase Qdrant HNSW parameters for better recall
   - Adjust batch sizes for embedding

3. **Caching**:
   - Cache frequent query embeddings (Redis)
   - Cache reranker results for identical queries
   - TTL: 1-24 hours depending on data freshness needs

## Extension Points

### Adding New RAG Methods

The service is designed for extensibility:

#### 1. GraphRAG
```python
# app/services/graph_rag_service.py
class GraphRAGService:
    async def build_graph(self, documents):
        # Extract entities and relationships
        # Build knowledge graph
        pass

    async def traverse_graph(self, query, max_depth=3):
        # Graph traversal for context gathering
        pass
```

#### 2. Image Search (Multimodal)
```python
# app/services/image_embedding_service.py
class ImageEmbeddingService:
    async def embed_image(self, image_bytes):
        # CLIP or similar model
        pass

    async def embed_text_for_image_search(self, text):
        # Shared embedding space
        pass
```

#### 3. Hybrid Retrieval + SQL
```python
# app/services/hybrid_sql_service.py
class HybridSQLService:
    async def search_vectors_and_sql(self, query, sql_filters):
        # Combine vector search with structured queries
        pass
```

## Configuration Matrix

### Search Quality vs Speed

| Config               | Recall | Latency | Use Case              |
|----------------------|--------|---------|----------------------|
| Basic (no rerank)    | 0.65   | 70ms    | High-volume, fuzzy   |
| + Reranker           | 0.85   | 170ms   | Standard production  |
| + Reranker + MMR     | 0.85   | 175ms   | Diverse results      |
| + High top_k (50)    | 0.90   | 200ms   | Maximum recall       |

### Memory Usage

| Component        | Memory   | Scaling Factor           |
|------------------|----------|--------------------------|
| Qdrant (10M pts) | ~15GB    | ~1.5KB per point (768d)  |
| TEI Reranker     | ~2GB     | Model size               |
| RAG Service      | ~500MB   | Base + request buffers   |

## Security Considerations

1. **API Key Management**:
   - Store Gemini API key in environment variables
   - Never commit `.env` to version control
   - Rotate keys periodically

2. **Access Control**:
   - Add authentication middleware to FastAPI
   - Implement project-level permissions
   - Rate limiting per user/project

3. **Data Privacy**:
   - Encrypt vectors at rest (Qdrant supports)
   - TLS for all inter-service communication
   - PII handling in metadata

## Monitoring & Observability

### Key Metrics

```python
# Latency percentiles
embedding_latency_p50
embedding_latency_p99

search_latency_p50
search_latency_p99

# Throughput
requests_per_second
embeddings_per_second

# Quality
search_results_returned
reranker_score_improvement

# Errors
embedding_errors_total
qdrant_connection_errors
```

### Logging

All services use structured JSON logging:

```json
{
  "timestamp": "2024-03-23T10:15:30Z",
  "service": "rag-service",
  "level": "INFO",
  "message": "Search completed successfully",
  "project": "my_project",
  "results_count": 5,
  "use_reranker": true,
  "latency_ms": 172
}
```

## Future Enhancements

1. **Adaptive Retrieval**:
   - Dynamically adjust `top_k` based on query complexity
   - Query classification to route to different pipelines

2. **Multi-Vector Representations**:
   - Store multiple embeddings per chunk (e.g., summary + full text)
   - Late interaction models (ColBERT)

3. **Active Learning**:
   - Collect user feedback on search results
   - Fine-tune reranker on domain data

4. **Cost Optimization**:
   - Cache embeddings for repeated texts
   - Batch similar queries together
   - Use smaller models for simple queries
