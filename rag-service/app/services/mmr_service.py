"""
MMR (Maximal Marginal Relevance) service for diversity filtering.
"""
import numpy as np
from typing import Any

from app.core import logger, settings


class MMRService:
    """Service for applying MMR diversity filter to search results."""

    def __init__(self):
        """Initialize MMR service."""
        self.lambda_param = settings.mmr_lambda
        logger.info(
            "MMR service initialized",
            extra={"lambda": self.lambda_param}
        )

    def apply_mmr(
        self,
        query_embedding: list[float],
        results: list[dict[str, Any]],
        top_n: int,
        lambda_param: float | None = None
    ) -> list[dict[str, Any]]:
        """
        Apply MMR to select diverse top-N results.

        MMR = λ * relevance(q, d) - (1 - λ) * max_similarity(d, selected)

        Args:
            query_embedding: Query embedding vector
            results: Search results with embeddings
            top_n: Number of diverse results to select
            lambda_param: Trade-off parameter (None = use default)

        Returns:
            Top-N diverse results
        """
        try:
            if len(results) <= top_n:
                return results

            lambda_val = lambda_param if lambda_param is not None else self.lambda_param

            # Extract embeddings and relevance scores
            query_vec = np.array(query_embedding)
            doc_embeddings = [
                np.array(r.get("embedding", r.get("dense_vector", [])))
                for r in results
            ]
            relevance_scores = [r["score"] for r in results]

            # Normalize relevance scores to 0-1
            min_score = min(relevance_scores)
            max_score = max(relevance_scores)
            score_range = max_score - min_score if max_score > min_score else 1.0
            normalized_scores = [
                (score - min_score) / score_range
                for score in relevance_scores
            ]

            # Initialize selected indices and candidates
            selected_indices = []
            candidate_indices = list(range(len(results)))

            # Select first document (highest relevance)
            first_idx = candidate_indices[0]
            selected_indices.append(first_idx)
            candidate_indices.remove(first_idx)

            # Iteratively select diverse documents
            while len(selected_indices) < top_n and candidate_indices:
                mmr_scores = []

                for idx in candidate_indices:
                    # Relevance term
                    relevance = normalized_scores[idx]

                    # Diversity term (max similarity to already selected)
                    max_similarity = 0.0
                    for selected_idx in selected_indices:
                        similarity = self._cosine_similarity(
                            doc_embeddings[idx],
                            doc_embeddings[selected_idx]
                        )
                        max_similarity = max(max_similarity, similarity)

                    # MMR score
                    mmr_score = lambda_val * relevance - (1 - lambda_val) * max_similarity
                    mmr_scores.append((idx, mmr_score))

                # Select document with highest MMR score
                best_idx, best_score = max(mmr_scores, key=lambda x: x[1])
                selected_indices.append(best_idx)
                candidate_indices.remove(best_idx)

            # Return selected results in order
            diverse_results = [results[idx] for idx in selected_indices]

            logger.info(
                "MMR filtering completed",
                extra={
                    "input_count": len(results),
                    "output_count": len(diverse_results),
                    "lambda": lambda_val,
                }
            )

            return diverse_results

        except Exception as e:
            logger.error(
                "MMR filtering failed",
                extra={"error": str(e)}
            )
            # Return original results if MMR fails
            return results[:top_n]

    @staticmethod
    def _cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity score
        """
        if len(vec1) == 0 or len(vec2) == 0:
            return 0.0

        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))


# Global MMR service instance
mmr_service = MMRService()
