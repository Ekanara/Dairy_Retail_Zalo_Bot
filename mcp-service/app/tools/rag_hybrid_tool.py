"""
rag_hybrid_tool.py — MCP Tool: Advanced RAG với hybrid search + reranking + MMR.

Sử dụng RAG service mới với:
- Hybrid search (dense + sparse vectors)
- RRF score fusion
- Neural reranking (TEI)
- MMR diversity filter
"""
import time
from typing import Any

import httpx
from pydantic import BaseModel

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

_TOOL_NAME = "rag_hybrid_search"


class RagHybridResult(BaseModel):
    """Kết quả từ advanced RAG service."""

    product_id: str
    product_name: str
    brand_name: str
    relevance_score: float
    text_snippet: str
    chunk_type: str  # main_info | purpose | usage
    price: float | None
    stock_quantity: int
    customer_segment: str | None
    customer_age: str | None
    origin: str | None


async def rag_hybrid_search_impl(
    question: str,
    top_n: int = 5,
    use_reranker: bool = True,
    use_mmr: bool = True,
) -> list[RagHybridResult]:
    """
    Advanced semantic search sử dụng RAG service.

    Pipeline:
    1. Embed query (dense + sparse)
    2. Hybrid search in Qdrant
    3. RRF score fusion
    4. Neural reranking (optional)
    5. MMR diversity filter (optional)

    Args:
        question: Câu hỏi / nhu cầu của người dùng
        top_n: Số kết quả trả về (mặc định 5)
        use_reranker: Dùng neural reranking (mặc định True)
        use_mmr: Dùng MMR diversity filter (mặc định True)

    Returns:
        Danh sách RagHybridResult sắp xếp theo relevance

    Raises:
        httpx.HTTPError: Lỗi kết nối RAG service
    """
    t0 = time.monotonic()

    # RAG service URL
    rag_service_url = settings.RAG_SERVICE_URL

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{rag_service_url}/api/v1/search",
                json={
                    "project_name": "magic_sale_products",
                    "query": question,
                    "top_k": 20,  # Initial retrieval
                    "top_n": top_n,  # Final results after reranking + MMR
                    "use_reranker": use_reranker,
                    "use_mmr": use_mmr,
                    "filters": {
                        # Only return products with stock
                        # Note: Filter implementation depends on metadata structure
                    }
                }
            )
            response.raise_for_status()
            data = response.json()

    except httpx.HTTPError as exc:
        logger.warning(
            "rag_hybrid_search_unavailable",
            extra={
                "tool_name": _TOOL_NAME,
                "question_snippet": question[:80],
                "error": str(exc),
                "rag_service_url": rag_service_url,
            },
        )
        return []

    # Parse results
    results: list[RagHybridResult] = []
    for item in data.get("results", []):
        metadata: dict[str, Any] = item.get("metadata", {})

        # Skip out-of-stock products (only filter if stock_quantity is explicitly present)
        stock_quantity = metadata.get("stock_quantity")
        if stock_quantity is not None and stock_quantity <= 0:
            continue

        results.append(
            RagHybridResult(
                product_id=metadata.get("product_id", metadata.get("source", "")),
                product_name=metadata.get("product_name", ""),
                brand_name=metadata.get("brand_name", ""),
                relevance_score=item.get("score", 0.0),
                text_snippet=item.get("text", "")[:200],  # Truncate for display
                chunk_type=metadata.get("chunk_type", "main_info"),
                price=metadata.get("price"),
                stock_quantity=stock_quantity if stock_quantity is not None else -1,
                customer_segment=metadata.get("customer_segment"),
                customer_age=metadata.get("customer_age"),
                origin=metadata.get("origin"),
            )
        )

    duration_ms = round((time.monotonic() - t0) * 1000, 2)

    logger.info(
        "rag_hybrid_search_done",
        extra={
            "tool_name": _TOOL_NAME,
            "question_snippet": question[:80],
            "result_count": len(results),
            "use_reranker": use_reranker,
            "use_mmr": use_mmr,
            "duration_ms": duration_ms,
        },
    )

    return results
