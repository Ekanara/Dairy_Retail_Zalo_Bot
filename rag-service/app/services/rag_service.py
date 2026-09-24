"""
Main RAG service orchestrating the full pipeline.
"""
import asyncio
from typing import Any
from qdrant_client.models import Filter, FieldCondition, MatchValue

from app.core import logger, settings
from app.models import (
    DocumentChunk,
    IngestionRequest,
    SearchRequest,
    SearchResult,
)
from app.repositories import qdrant_repository
from app.services.embedding_service import embedding_service
from app.services.sparse_embedding_service import sparse_embedding_service
from app.services.reranker_service import reranker_service
from app.services.mmr_service import mmr_service


class RAGService:
    """Main RAG service implementing the full pipeline."""

    def __init__(self):
        """Initialize RAG service."""
        self.qdrant = qdrant_repository
        self.embedding = embedding_service
        self.sparse_embedding = sparse_embedding_service
        self.reranker = reranker_service
        self.mmr = mmr_service
        logger.info("RAG service initialized")

    async def ingest_documents(self, request: IngestionRequest) -> dict[str, Any]:
        """
        Ingest documents into the RAG system.

        Pipeline: chunk → embed (dense + sparse) → upsert to Qdrant

        Args:
            request: Ingestion request with project name and chunks

        Returns:
            Ingestion result dictionary
        """
        try:
            # Ensure collection exists
            await self._ensure_collection(request.project_name)

            # Extract texts from chunks
            texts = [chunk.text for chunk in request.chunks]

            # Generate embeddings in parallel
            dense_embeddings_task = self.embedding.embed_documents(texts)
            sparse_embeddings_task = asyncio.to_thread(
                self.sparse_embedding.embed_documents,
                texts
            )

            dense_embeddings, sparse_embeddings = await asyncio.gather(
                dense_embeddings_task,
                sparse_embeddings_task,
            )

            # Prepare points for upsert
            points = []
            for i, chunk in enumerate(request.chunks):
                points.append({
                    "id": chunk.id,
                    "dense_vector": dense_embeddings[i],
                    "sparse_vector": sparse_embeddings[i],
                    "payload": {
                        "text": chunk.text,
                        "source": chunk.metadata.source,
                        "date": chunk.metadata.date,
                        "lang": chunk.metadata.lang,
                        "chunk_index": chunk.metadata.chunk_index,
                        "total_chunks": chunk.metadata.total_chunks,
                        **chunk.metadata.extra,
                    }
                })

            # Upsert to Qdrant
            await self.qdrant.upsert_points(
                collection_name=request.project_name,
                points=points,
            )

            logger.info(
                "Documents ingested successfully",
                extra={
                    "project": request.project_name,
                    "chunks": len(request.chunks),
                }
            )

            return {
                "project_name": request.project_name,
                "chunks_ingested": len(request.chunks),
                "status": "success",
            }

        except Exception as e:
            logger.error(
                "Document ingestion failed",
                extra={"project": request.project_name, "error": str(e)}
            )
            raise

    async def search(self, request: SearchRequest) -> dict[str, Any]:
        """
        Perform RAG search with the full pipeline.

        Pipeline:
        1. Embed query (dense + sparse)
        2. Hybrid search (dense + sparse + filter)
        3. Re-rank (RRF score fusion + TEI reranker)
        4. MMR filter (diversity)
        5. LLM generation (delegated to caller)

        Args:
            request: Search request with query and parameters

        Returns:
            Search results dictionary
        """
        try:
            # Get parameters with defaults
            top_k = request.top_k or settings.default_top_k
            top_n = request.top_n or settings.default_top_n

            # Step 1: Embed query
            query_embedding_task = self.embedding.embed_query(request.query)
            sparse_query_task = asyncio.to_thread(
                self.sparse_embedding.embed_query,
                request.query
            )

            query_embedding, sparse_query = await asyncio.gather(
                query_embedding_task,
                sparse_query_task,
            )

            # Step 2: Hybrid search
            query_filter = self._build_filter(request.filters) if request.filters else None

            search_results = await self.qdrant.hybrid_search(
                collection_name=request.project_name,
                dense_vector=query_embedding,
                sparse_vector=sparse_query,
                limit=top_k,
                query_filter=query_filter,
            )

            if not search_results:
                return {
                    "project_name": request.project_name,
                    "query": request.query,
                    "results": [],
                    "total_results": 0,
                }

            # Step 3: Reranking (optional, graceful fallback)
            if request.use_reranker:
                try:
                    # Extract texts for reranking
                    texts = [r["payload"]["text"] for r in search_results]

                    # Get reranker scores
                    reranked = await self.reranker.rerank(
                        query=request.query,
                        documents=texts,
                        top_n=None,  # Rerank all, filter later
                    )

                    # Apply reranker scores to results
                    for i, rerank_result in enumerate(reranked):
                        idx = rerank_result["index"]
                        search_results[idx]["score"] = rerank_result["score"]

                    # Sort by reranker score
                    search_results.sort(key=lambda x: x["score"], reverse=True)
                except Exception as rerank_err:
                    logger.warning(
                        "Reranker unavailable, skipping rerank step",
                        extra={"error": str(rerank_err)},
                    )

            # Step 4: MMR diversity filter (optional)
            if request.use_mmr and len(search_results) > top_n:
                # Add query embedding to results for MMR
                for result in search_results:
                    result["query_embedding"] = query_embedding

                search_results = self.mmr.apply_mmr(
                    query_embedding=query_embedding,
                    results=search_results,
                    top_n=top_n,
                )
            else:
                # Just take top_n
                search_results = search_results[:top_n]

            # Convert to response format
            results = [
                SearchResult(
                    id=str(r["id"]),
                    text=r["payload"]["text"],
                    score=r["score"],
                    metadata={
                        k: v for k, v in r["payload"].items()
                        if k != "text"
                    }
                )
                for r in search_results
            ]

            logger.info(
                "Search completed successfully",
                extra={
                    "project": request.project_name,
                    "results_count": len(results),
                    "use_reranker": request.use_reranker,
                    "use_mmr": request.use_mmr,
                }
            )

            return {
                "project_name": request.project_name,
                "query": request.query,
                "results": results,
                "total_results": len(results),
            }

        except Exception as e:
            logger.error(
                "Search failed",
                extra={"project": request.project_name, "error": str(e)}
            )
            raise

    async def _ensure_collection(self, collection_name: str) -> None:
        """
        Ensure collection exists, create if not.

        Args:
            collection_name: Name of the collection
        """
        try:
            await self.qdrant.create_collection(collection_name)
        except Exception:
            # Collection might already exist, that's ok
            pass

    @staticmethod
    def _build_filter(filters: dict[str, Any]) -> Filter | None:
        """
        Build Qdrant filter from filter dictionary.

        Args:
            filters: Dictionary of field: value filters

        Returns:
            Qdrant Filter object or None
        """
        if not filters:
            return None

        conditions = []
        for field, value in filters.items():
            conditions.append(
                FieldCondition(
                    key=field,
                    match=MatchValue(value=value),
                )
            )

        if not conditions:
            return None

        return Filter(must=conditions)


# Global RAG service instance
rag_service = RAGService()
