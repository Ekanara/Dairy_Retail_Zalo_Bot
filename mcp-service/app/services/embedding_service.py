"""
embedding_service.py — Gọi Gemma 3 0.3B (Ollama / OpenAI-compatible) để lấy embedding vector.
"""
import httpx
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


async def get_embedding(text: str) -> list[float]:
    """
    Gửi `text` tới Gemma 0.3B embedding endpoint (Ollama OpenAI-compat).

    Returns:
        list[float]: vector embedding.

    Raises:
        httpx.HTTPStatusError: nếu endpoint trả lỗi HTTP.
        httpx.RequestError: nếu mạng lỗi / timeout.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{settings.EMBEDDING_BASE_URL}/embeddings",
                headers={"Authorization": f"Bearer {settings.EMBEDDING_API_KEY}"},
                json={
                    "model": settings.EMBEDDING_MODEL_NAME,
                    "input": text,
                },
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "embedding_http_error",
                extra={
                    "event": "embedding_failed",
                    "status_code": exc.response.status_code,
                    "text_snippet": text[:80],
                    "model": settings.EMBEDDING_MODEL_NAME,
                },
            )
            raise
        except httpx.RequestError as exc:
            logger.error(
                "embedding_request_error",
                extra={
                    "event": "embedding_failed",
                    "error": str(exc),
                    "text_snippet": text[:80],
                },
            )
            raise

        data = response.json()
        embedding: list[float] = data["data"][0]["embedding"]
        logger.debug(
            "embedding_ok",
            extra={
                "event": "embedding_success",
                "model": settings.EMBEDDING_MODEL_NAME,
                "dim": len(embedding),
                "text_snippet": text[:80],
            },
        )
        return embedding
