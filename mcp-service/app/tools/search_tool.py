"""
search_tool.py — MCP Tool: tìm kiếm sản phẩm theo từ khoá (ILIKE) trong PostgreSQL.
"""
import time
import re

import asyncpg.exceptions
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.logger import get_logger
from app.db.database import get_session

logger = get_logger(__name__)

_TOOL_NAME = "search_keyword"
_VI_STOPWORDS = {
    "cho", "va", "và", "la", "là", "co", "có", "khong", "không",
    "toi", "tôi", "ban", "bạn", "nhu", "như", "duoc", "được",
    "tre", "trẻ", "nguoi", "người", "giup", "giúp", "tu", "từ",
}

# ---------------------------------------------------------------------------
# Vietnamese → ENUM mapping tables
# ---------------------------------------------------------------------------
_SEGMENT_MAP: dict[str, str] = {
    # Vietnamese keywords → customer_segment enum value
    "tre em": "children", "trẻ em": "children", "be": "children", "bé": "children",
    "em be": "children", "em bé": "children", "tre con": "children", "trẻ con": "children",
    "nhi": "children",
    "nguoi gia": "elderly", "người già": "elderly", "nguoi lon tuoi": "elderly",
    "người lớn tuổi": "elderly", "cao tuoi": "elderly", "cao tuổi": "elderly",
    "ong": "elderly", "ông": "elderly", "ba": "elderly", "bà": "elderly",
    "phu nu": "women", "phụ nữ": "women", "nu gioi": "women", "nữ giới": "women",
    "benh nhan": "patients", "bệnh nhân": "patients", "nguoi benh": "patients",
    "người bệnh": "patients", "phuc hoi": "patients", "phục hồi": "patients",
    "me cho con bu": "breastfeeding_mothers", "mẹ cho con bú": "breastfeeding_mothers",
    "cho con bu": "breastfeeding_mothers", "cho con bú": "breastfeeding_mothers",
    "dang cho bu": "breastfeeding_mothers", "đang cho bú": "breastfeeding_mothers",
    "me bau": "pregnant_mothers", "mẹ bầu": "pregnant_mothers",
    "mang thai": "pregnant_mothers", "bau": "pregnant_mothers", "bầu": "pregnant_mothers",
    "thai ky": "pregnant_mothers", "thai kỳ": "pregnant_mothers",
    "tieu duong": "diabetic", "tiểu đường": "diabetic", "dai thao duong": "diabetic",
    "đái tháo đường": "diabetic", "duong huyet": "diabetic", "đường huyết": "diabetic",
}

def _detect_segment(query: str) -> str | None:
    """Detect customer_segment enum value from Vietnamese query."""
    q = query.lower()
    # Check longest phrases first to avoid partial matches
    for phrase in sorted(_SEGMENT_MAP, key=len, reverse=True):
        if phrase in q:
            return _SEGMENT_MAP[phrase]
    return None


def _detect_age(query: str) -> str | None:
    """
    Extract age from Vietnamese query and map to customer_age enum.
    Examples:
        "trẻ 6 tháng" → age_0m_6m
        "bé 2 tuổi" → age_6m_36m
        "trẻ 8 tuổi" → age_4y_12y
    """
    q = query.lower()
    # Match patterns like "6 tháng", "2 tuổi", "6 thang", "2 tuoi"
    m_month = re.search(r"(\d+)\s*(?:tháng|thang)", q)
    m_year = re.search(r"(\d+)\s*(?:tuổi|tuoi)", q)

    age_months: int | None = None
    if m_month:
        age_months = int(m_month.group(1))
    elif m_year:
        age_months = int(m_year.group(1)) * 12

    if age_months is None:
        return None

    if age_months <= 6:
        return "age_0m_6m"
    elif age_months <= 36:
        return "age_6m_36m"
    elif age_months <= 12 * 12:
        return "age_4y_12y"
    elif age_months <= 17 * 12:
        return "age_13y_17y"
    elif age_months <= 40 * 12:
        return "age_18y_40y"
    elif age_months <= 60 * 12:
        return "age_41y_60y"
    else:
        return "age_60y_plus"


def _clean_html(text: str, max_len: int = 200) -> str:
    """Remove HTML/CSS junk and truncate to max_len."""
    if not text:
        return ""
    # Remove HTML tags and CSS
    cleaned = re.sub(r'<[^>]+>', '', text)
    cleaned = re.sub(r'#html-body\s*\[.*?\]\{[^}]*\}', '', cleaned)
    cleaned = re.sub(r'\{[^}]*\}', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len] + "..."
    return cleaned


class ProductResult(BaseModel):
    """Kết quả trả về cho mỗi sản phẩm tìm được."""
    product_id: str
    name: str
    brand_name: str
    origin: str
    customer_segment: str
    customer_age: str
    product_purpose: str
    how_use: str
    price: int
    stock_quantity: int

    def to_clean_dict(self) -> dict:
        """Return a concise dict for LLM consumption — no HTML junk."""
        return {
            "product_id": self.product_id,
            "name": self.name,
            "brand_name": self.brand_name,
            "price": self.price,
            "product_purpose": _clean_html(self.product_purpose),
            "how_use": _clean_html(self.how_use, 100),
            "stock_quantity": self.stock_quantity,
        }


async def search_keyword_impl(
    query: str,
) -> list[ProductResult]:
    """
    Tìm kiếm sản phẩm trong bảng `products` theo `name`, `brand`,
    `customer_segment`, `product_purpose` bằng ILIKE (case-insensitive).

    Args:
        query: Từ khoá cần tìm.

    Returns:
        Danh sách ProductResult còn hàng (stock_quantity > 0).

    Raises:
        DBAPIError: Lỗi truy vấn DB.
    """
    limit = 10
    t0 = time.monotonic()

    sql = text("""
        SELECT
            p.product_id::text,
            p.name,
            COALESCE(b.name, '') AS brand_name,
            COALESCE(p.origin::text, '') AS origin,
            COALESCE(p.customer_segment::text, '') AS customer_segment,
            COALESCE(p.customer_age::text, '') AS customer_age,
            COALESCE(p.product_purpose, '') AS product_purpose,
            COALESCE(p.how_use, '') AS how_use,
            COALESCE(p.price::int, 0) AS price,
            p.stock_quantity
        FROM products p
        LEFT JOIN brands b ON p.brand_id = b.brand_id
        WHERE
            (
                p.name             ILIKE :q
                OR b.name          ILIKE :q
                OR p.customer_segment::text ILIKE :q
                OR p.product_purpose  ILIKE :q
            )
            AND p.stock_quantity > 0
        ORDER BY p.name
        LIMIT :limit
    """)

    try:
        async with get_session() as session:
            result = await session.execute(
                sql,
                {"q": f"%{query}%", "limit": limit},
            )
            rows = result.fetchall()
    except DBAPIError as exc:
        logger.error(
            "search_keyword_db_error",
            extra={
                "tool_name": _TOOL_NAME,
                "query": query,
                "error": str(exc),
            },
        )
        raise

    products = [ProductResult(**dict(row._mapping)) for row in rows]

    # Fallback 2: token-aware search (for long natural-language questions)
    if not products:
        token_products = await _search_by_tokens(query=query, limit=10)
        if token_products:
            products = token_products

    duration_ms = round((time.monotonic() - t0) * 1000, 2)

    logger.info(
        "search_keyword_done",
        extra={
            "tool_name": _TOOL_NAME,
            "query": query,
            "result_count": len(products),
            "duration_ms": duration_ms,
        },
    )
    return products


def _extract_tokens(query: str) -> list[str]:
    raw_tokens = re.findall(r"[0-9A-Za-zÀ-ỹà-ỹ]+", query.lower())
    tokens: list[str] = []
    for tok in raw_tokens:
        if len(tok) < 2:
            continue
        if tok in _VI_STOPWORDS:
            continue
        tokens.append(tok)
    # Keep stable order while removing duplicates
    deduped = list(dict.fromkeys(tokens))
    return deduped[:6]


async def _search_by_tokens(query: str, limit: int) -> list[ProductResult]:
    tokens = _extract_tokens(query)
    if not tokens:
        return []

    score_expr_parts: list[str] = []
    params: dict[str, object] = {"limit": limit}
    for i, _tok in enumerate(tokens):
        param_key = f"t{i}"
        params[param_key] = f"%{_tok}%"
        score_expr_parts.append(
            f"""
            (
                CASE
                    WHEN p.name ILIKE :{param_key}
                      OR b.name ILIKE :{param_key}
                      OR p.customer_segment::text ILIKE :{param_key}
                      OR p.product_purpose ILIKE :{param_key}
                    THEN 1 ELSE 0
                END
            )
            """
        )

    score_expr = " + ".join(score_expr_parts)
    sql = text(f"""
        SELECT
            p.product_id::text,
            p.name,
            COALESCE(b.name, '') AS brand_name,
            COALESCE(p.origin::text, '') AS origin,
            COALESCE(p.customer_segment::text, '') AS customer_segment,
            COALESCE(p.customer_age::text, '') AS customer_age,
            COALESCE(p.product_purpose, '') AS product_purpose,
            COALESCE(p.how_use, '') AS how_use,
            COALESCE(p.price::int, 0) AS price,
            p.stock_quantity,
            ({score_expr}) AS match_score
        FROM products p
        LEFT JOIN brands b ON p.brand_id = b.brand_id
        WHERE p.stock_quantity > 0
        ORDER BY match_score DESC, p.name
        LIMIT :limit
    """)

    async with get_session() as session:
        result = await session.execute(sql, params)
        rows = result.fetchall()

    filtered_rows = [row for row in rows if int(row._mapping.get("match_score", 0)) > 0]
    return [ProductResult(**{k: v for k, v in dict(row._mapping).items() if k != "match_score"}) for row in filtered_rows]


async def search_by_segment_impl(
    query: str,
) -> list[ProductResult]:
    """Search products by detecting customer_segment from Vietnamese query."""
    limit = 10
    t0 = time.monotonic()
    segment = _detect_segment(query)

    if segment is None:
        # Fallback to keyword search
        return await search_keyword_impl(query)

    sql = text("""
        SELECT
            p.product_id::text,
            p.name,
            COALESCE(b.name, '') AS brand_name,
            COALESCE(p.origin::text, '') AS origin,
            COALESCE(p.customer_segment::text, '') AS customer_segment,
            COALESCE(p.customer_age::text, '') AS customer_age,
            COALESCE(p.product_purpose, '') AS product_purpose,
            COALESCE(p.how_use, '') AS how_use,
            COALESCE(p.price::int, 0) AS price,
            p.stock_quantity
        FROM products p
        LEFT JOIN brands b ON p.brand_id = b.brand_id
        WHERE p.customer_segment = CAST(:segment AS customer_segment)
          AND p.stock_quantity > 0
        ORDER BY p.name
        LIMIT :limit
    """)

    try:
        async with get_session() as session:
            result = await session.execute(sql, {"segment": segment, "limit": limit})
            rows = result.fetchall()
    except DBAPIError as exc:
        logger.error("search_segment_db_error", extra={"tool_name": "search_segment", "query": query, "error": str(exc)})
        raise

    products = [ProductResult(**dict(row._mapping)) for row in rows]

    # Fallback: if segment-based search returns nothing, try keyword with brand
    if not products:
        brand_map = {
            "children": "PediaSure",
            "elderly": "Ensure Gold",
            "diabetic": "Glucerna",
            "pregnant_mothers": "Similac Mom",
            "breastfeeding_mothers": "Similac Mom",
        }
        fallback_brand = brand_map.get(segment, "Ensure")
        products = await search_keyword_impl(fallback_brand)

    duration_ms = round((time.monotonic() - t0) * 1000, 2)
    logger.info("search_segment_done", extra={"tool_name": "search_segment", "query": query, "detected_segment": segment, "result_count": len(products), "duration_ms": duration_ms})
    return products


async def search_by_age_impl(
    query: str,
) -> list[ProductResult]:
    """Search products by detecting customer_age from Vietnamese query."""
    limit = 10
    t0 = time.monotonic()
    age = _detect_age(query)

    if age is None:
        return await search_keyword_impl(query)

    sql = text("""
        SELECT
            p.product_id::text,
            p.name,
            COALESCE(b.name, '') AS brand_name,
            COALESCE(p.origin::text, '') AS origin,
            COALESCE(p.customer_segment::text, '') AS customer_segment,
            COALESCE(p.customer_age::text, '') AS customer_age,
            COALESCE(p.product_purpose, '') AS product_purpose,
            COALESCE(p.how_use, '') AS how_use,
            COALESCE(p.price::int, 0) AS price,
            p.stock_quantity
        FROM products p
        LEFT JOIN brands b ON p.brand_id = b.brand_id
        WHERE (p.customer_age = CAST(:age AS customer_age) OR p.customer_age = 'all_ages')
          AND p.stock_quantity > 0
        ORDER BY p.name
        LIMIT :limit
    """)

    try:
        async with get_session() as session:
            result = await session.execute(sql, {"age": age, "limit": limit})
            rows = result.fetchall()
    except DBAPIError as exc:
        logger.error("search_age_db_error", extra={"tool_name": "search_age", "query": query, "error": str(exc)})
        raise

    products = [ProductResult(**dict(row._mapping)) for row in rows]

    # Fallback: if age-based search returns nothing, try keyword search with brand
    if not products:
        age_months = int(re.search(r"(\d+)", query).group(1)) * 12 if re.search(r"(\d+)\s*(?:tuổi|tuoi)", query.lower()) else 0
        if age_months <= 12 * 12:
            # Child → search PediaSure or Similac
            products = await search_keyword_impl("PediaSure")
        elif age_months <= 60 * 12:
            products = await search_keyword_impl("Ensure Gold")
        else:
            products = await search_keyword_impl("Ensure Gold")

    duration_ms = round((time.monotonic() - t0) * 1000, 2)
    logger.info("search_age_done", extra={"tool_name": "search_age", "query": query, "detected_age": age, "result_count": len(products), "duration_ms": duration_ms})
    return products


class BrandResult(BaseModel):
    """Kết quả trả về cho mỗi thương hiệu."""
    brand_id: str
    name: str


async def list_brands_impl() -> list[BrandResult]:
    """List all available brands."""
    t0 = time.monotonic()
    sql = text("""
        SELECT brand_id::text, name
        FROM brands
        ORDER BY name
    """)

    try:
        async with get_session() as session:
            result = await session.execute(sql)
            rows = result.fetchall()
    except DBAPIError as exc:
        logger.error("list_brands_db_error", extra={"tool_name": "list_brands", "error": str(exc)})
        raise

    brands = [BrandResult(**dict(row._mapping)) for row in rows]
    duration_ms = round((time.monotonic() - t0) * 1000, 2)
    logger.info("list_brands_done", extra={"tool_name": "list_brands", "result_count": len(brands), "duration_ms": duration_ms})
    return brands


async def search_by_brand_impl(
    brand_name: str,
) -> list[ProductResult]:
    """Search products by brand name (exact or ILIKE match)."""
    limit = 10
    t0 = time.monotonic()

    sql = text("""
        SELECT
            p.product_id::text,
            p.name,
            COALESCE(b.name, '') AS brand_name,
            COALESCE(p.origin::text, '') AS origin,
            COALESCE(p.customer_segment::text, '') AS customer_segment,
            COALESCE(p.customer_age::text, '') AS customer_age,
            COALESCE(p.product_purpose, '') AS product_purpose,
            COALESCE(p.how_use, '') AS how_use,
            COALESCE(p.price::int, 0) AS price,
            p.stock_quantity
        FROM products p
        JOIN brands b ON p.brand_id = b.brand_id
        WHERE b.name ILIKE :brand_name
          AND p.stock_quantity > 0
        ORDER BY p.name
        LIMIT :limit
    """)

    try:
        async with get_session() as session:
            result = await session.execute(sql, {"brand_name": f"%{brand_name}%", "limit": limit})
            rows = result.fetchall()
    except DBAPIError as exc:
        logger.error("search_brand_db_error", extra={"tool_name": "search_brand", "brand_name": brand_name, "error": str(exc)})
        raise

    products = [ProductResult(**dict(row._mapping)) for row in rows]
    duration_ms = round((time.monotonic() - t0) * 1000, 2)
    logger.info("search_brand_done", extra={"tool_name": "search_brand", "brand_name": brand_name, "result_count": len(products), "duration_ms": duration_ms})
    return products
