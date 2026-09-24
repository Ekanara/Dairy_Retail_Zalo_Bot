"""
Sparse embedding service using FastEmbed for BM25.
"""
from fastembed import SparseTextEmbedding
from typing import Any

from app.core import logger


class SparseEmbeddingService:
    """Service for generating sparse embeddings (BM25)."""

    def __init__(self):
        """Initialize sparse embedding service."""
        self.model = SparseTextEmbedding(model_name="Qdrant/bm25")
        logger.info("Sparse embedding service initialized with BM25")

    def embed_text(self, text: str | list[str]) -> list[dict[str, Any]]:
        """
        Generate sparse embeddings for text.

        Args:
            text: Single text string or list of text strings

        Returns:
            List of sparse embedding dictionaries with indices and values
        """
        try:
            texts = [text] if isinstance(text, str) else text

            # Generate sparse embeddings
            embeddings = list(self.model.embed(texts))

            # Convert to Qdrant sparse vector format
            sparse_vectors = []
            for embedding in embeddings:
                sparse_vectors.append({
                    "indices": embedding.indices.tolist(),
                    "values": embedding.values.tolist(),
                })

            logger.info(
                "Sparse embeddings generated",
                extra={"num_texts": len(texts)}
            )

            return sparse_vectors

        except Exception as e:
            logger.error(
                "Failed to generate sparse embeddings",
                extra={"error": str(e)}
            )
            raise

    def embed_query(self, query: str) -> dict[str, Any]:
        """
        Generate sparse embedding for a search query.

        Args:
            query: Search query text

        Returns:
            Sparse embedding dictionary with indices and values
        """
        return self.embed_text(query)[0]

    def embed_documents(self, documents: list[str]) -> list[dict[str, Any]]:
        """
        Generate sparse embeddings for multiple documents.

        Args:
            documents: List of document texts

        Returns:
            List of sparse embedding dictionaries
        """
        return self.embed_text(documents)


# Global sparse embedding service instance
sparse_embedding_service = SparseEmbeddingService()
