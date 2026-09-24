"""
Embedding service using OpenAI-compatible SDK for Gemini.
"""
from typing import Literal
from openai import AsyncOpenAI

from app.core import logger, settings


class EmbeddingService:
    """Service for generating embeddings using OpenAI-compatible API."""

    def __init__(self):
        """Initialize embedding service with Gemini configuration."""
        self.client = AsyncOpenAI(
            api_key=settings.gemini_api_key,
            base_url=settings.gemini_api_embedding_url,
        )
        self.model_name = settings.embedding_model_name
        logger.info(
            "Embedding service initialized",
            extra={
                "model": self.model_name,
                "base_url": settings.gemini_api_embedding_url,
            }
        )

    async def embed_text(
        self,
        text: str | list[str],
        task_type: Literal["RETRIEVAL_QUERY", "RETRIEVAL_DOCUMENT"] = "RETRIEVAL_DOCUMENT"
    ) -> tuple[list[list[float]], dict[str, int]]:
        """
        Generate embeddings for text using Gemini embedding model.

        Args:
            text: Single text string or list of text strings
            task_type: Task type for embedding optimization

        Returns:
            Tuple of (embeddings, usage_dict)
        """
        try:
            # Ensure text is a list
            texts = [text] if isinstance(text, str) else text

            # Generate embeddings using OpenAI-compatible API
            response = await self.client.embeddings.create(
                model=self.model_name,
                input=texts,
                encoding_format="float",
            )

            # Extract embeddings
            embeddings = [item.embedding for item in response.data]

            # Extract usage information
            usage = {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            }

            logger.info(
                "Embeddings generated",
                extra={
                    "num_texts": len(texts),
                    "task_type": task_type,
                    "usage": usage,
                }
            )

            return embeddings, usage

        except Exception as e:
            logger.error(
                "Failed to generate embeddings",
                extra={"error": str(e), "task_type": task_type}
            )
            raise

    async def embed_query(self, query: str) -> list[float]:
        """
        Generate embedding for a search query.

        Args:
            query: Search query text

        Returns:
            Query embedding vector
        """
        embeddings, _ = await self.embed_text(query, task_type="RETRIEVAL_QUERY")
        return embeddings[0]

    async def embed_documents(self, documents: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple documents.

        Args:
            documents: List of document texts

        Returns:
            List of document embedding vectors
        """
        embeddings, _ = await self.embed_text(documents, task_type="RETRIEVAL_DOCUMENT")
        return embeddings


# Global embedding service instance
embedding_service = EmbeddingService()
