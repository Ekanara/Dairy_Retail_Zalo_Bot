"""
Reranking service using TEI (Text Embeddings Inference).
"""
import httpx
from typing import Any

from app.core import logger, settings


class RerankerService:
    """Service for reranking search results using TEI."""

    def __init__(self):
        """Initialize reranker service."""
        self.base_url = settings.tei_reranker_url
        self.timeout = httpx.Timeout(30.0)
        logger.info(
            "Reranker service initialized",
            extra={"url": self.base_url}
        )

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int | None = None
    ) -> list[dict[str, Any]]:
        """
        Rerank documents using TEI reranker.

        Args:
            query: Search query
            documents: List of document texts to rerank
            top_n: Number of top results to return (None = return all)

        Returns:
            List of reranked results with index and score
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/rerank",
                    json={
                        "query": query,
                        "texts": documents,
                        "truncate": True,
                    }
                )
                response.raise_for_status()

                results = response.json()

                # Sort by score descending
                sorted_results = sorted(
                    results,
                    key=lambda x: x.get("score", 0),
                    reverse=True
                )

                # Limit to top_n if specified
                if top_n is not None:
                    sorted_results = sorted_results[:top_n]

                logger.info(
                    "Reranking completed",
                    extra={
                        "num_documents": len(documents),
                        "top_n": top_n or len(documents),
                    }
                )

                return sorted_results

        except httpx.HTTPError as e:
            logger.error(
                "Reranking request failed",
                extra={"error": str(e)}
            )
            raise
        except Exception as e:
            logger.error(
                "Reranking failed",
                extra={"error": str(e)}
            )
            raise

    async def rrf_fusion(
        self,
        dense_results: list[dict[str, Any]],
        sparse_results: list[dict[str, Any]],
        k: int = 60
    ) -> list[dict[str, Any]]:
        """
        Apply Reciprocal Rank Fusion (RRF) to combine dense and sparse search results.

        Args:
            dense_results: Results from dense vector search
            sparse_results: Results from sparse vector search
            k: RRF constant (default 60)

        Returns:
            Fused and reranked results
        """
        try:
            # Calculate RRF scores
            rrf_scores: dict[str, float] = {}

            # Process dense results
            for rank, result in enumerate(dense_results, start=1):
                doc_id = result["id"]
                rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1 / (k + rank)

            # Process sparse results
            for rank, result in enumerate(sparse_results, start=1):
                doc_id = result["id"]
                rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1 / (k + rank)

            # Create merged results with RRF scores
            results_map = {}
            for result in dense_results + sparse_results:
                results_map[result["id"]] = result

            fused_results = [
                {
                    **results_map[doc_id],
                    "score": score,
                }
                for doc_id, score in rrf_scores.items()
            ]

            # Sort by RRF score
            fused_results.sort(key=lambda x: x["score"], reverse=True)

            logger.info(
                "RRF fusion completed",
                extra={
                    "dense_count": len(dense_results),
                    "sparse_count": len(sparse_results),
                    "fused_count": len(fused_results),
                }
            )

            return fused_results

        except Exception as e:
            logger.error(
                "RRF fusion failed",
                extra={"error": str(e)}
            )
            raise

    async def health_check(self) -> bool:
        """
        Check if reranker service is healthy.

        Returns:
            True if reranker is healthy
        """
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception:
            return False


# Global reranker service instance
reranker_service = RerankerService()
