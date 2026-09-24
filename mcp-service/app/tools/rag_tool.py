"""
rag_tool.py — MCP Tool: semantic search với Gemma 3 0.3B embedding + pgvector.
"""
import time

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.logger import get_logger
from app.db.database import get_session
from app.services.embedding_service import get_embedding

logger = get_logger(__name__)

_TOOL_NAME = "rag_search"


class RagResult(BaseModel):
    """Kết quả semantic search trả về cho mỗi sản phẩm."""

    product_id: str
    name: str
    brand_name: str
    similarity_score: float
    product_purpose: str
    price: int


async def rag_search_impl(
    question: str,
    top_k: int = 3,
) -> list[RagResult]:
    """
    Semantic search:
      1. Embed `question` bằng Gemma 3 0.3B (Ollama OpenAI-compat).
      2. Cosine similarity với cột `embedding` (pgvector) trong bảng `products`.
      3. Trả top_k sản phẩm còn hàng có similarity cao nhất.

    Args:
        question: Câu hỏi / nhu cầu của người dùng.
        top_k: Số sản phẩm trả về (mặc định 3).

    Returns:
        Danh sách RagResult sắp xếp theo similarity giảm dần.

    Raises:
        httpx.HTTPStatusError | httpx.RequestError: Lỗi embedding endpoint.
        DBAPIError: Lỗi truy vấn DB / pgvector.
    """
    t0 = time.monotonic()

    # --- 1. Lấy embedding vector ---
    try:
        embedding: list[float] = await get_embedding(question)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "rag_search_embedding_unavailable",
            extra={
                "tool_name": _TOOL_NAME,
                "question_snippet": question[:80],
                "error": str(exc),
            },
        )
        return []

    # Chuyển list float → chuỗi pgvector: "[0.1,0.2,...]"
    vec_str = "[" + ",".join(map(str, embedding)) + "]"

    # --- 2. Cosine search trong pgvector ---
    sql = text("""
        SELECT
            p.product_id::text,
            p.name,
            COALESCE(b.name, '') AS brand_name,
            p.product_purpose,
            p.price::int,
            1 - (p.embedding <=> CAST(:vec AS vector)) AS similarity_score
        FROM products p
        LEFT JOIN brands b ON p.brand_id = b.brand_id
        WHERE
            p.embedding IS NOT NULL
            AND p.stock_quantity > 0
        ORDER BY p.embedding <=> CAST(:vec AS vector)
        LIMIT :top_k
    """)

    try:
        async with get_session() as session:
            result = await session.execute(
                sql,
                {"vec": vec_str, "top_k": top_k},
            )
            rows = result.fetchall()
    except DBAPIError as exc:
        logger.warning(
            "rag_search_db_error",
            extra={
                "tool_name": _TOOL_NAME,
                "question_snippet": question[:80],
                "error": str(exc),
            },
        )
        return []

    results = [RagResult(**dict(row._mapping)) for row in rows]
    duration_ms = round((time.monotonic() - t0) * 1000, 2)

    logger.info(
        "rag_search_done",
        extra={
            "tool_name": _TOOL_NAME,
            "question_snippet": question[:80],
            "embedding_dim": len(embedding),
            "result_count": len(results),
            "duration_ms": duration_ms,
        },
    )
    return results
