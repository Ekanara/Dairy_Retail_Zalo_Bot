"""
server.py — FastMCP server: 9 MCP tools cho AI agent.
"""
import copy
from collections.abc import Sequence
from typing import Literal

from fastmcp import FastMCP
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools.tool import Tool
import mcp.types as mt

from app.core.logger import get_logger
from app.tools.order_tool import OrderConfirmation, OrderItem, create_order_impl
from app.tools.personal_tool import (
    ProfileEditResult,
    edit_profile_impl,
    view_profile_impl,
)
from app.tools.rag_tool import RagResult, rag_search_impl
from app.tools.rag_hybrid_tool import RagHybridResult, rag_hybrid_search_impl
from app.tools.search_tool import (
    BrandResult,
    ProductResult,
    list_brands_impl,
    search_by_age_impl,
    search_by_brand_impl,
    search_by_segment_impl,
    search_keyword_impl,
)

logger = get_logger(__name__)

# Tools whose `user_id` param must be hidden from the model.
# The param stays in the function signature (server accepts it),
# but the middleware strips it from the JSON schema the model sees.
# models-service's _inject_user_id_hook adds the real value at call time.
_TOOLS_WITH_USER_ID = frozenset({
    "create_order",
    "view_personal_profile",
    "edit_personal_profile",
})


class HideUserIdMiddleware(Middleware):
    """Strip ``user_id`` from tool schemas so the model cannot see or hallucinate it."""

    async def on_list_tools(
        self,
        context: MiddlewareContext[mt.ListToolsRequest],
        call_next: CallNext[mt.ListToolsRequest, Sequence[Tool]],
    ) -> Sequence[Tool]:
        tools = await call_next(context)
        result: list[Tool] = []
        for tool in tools:
            if tool.name in _TOOLS_WITH_USER_ID:
                params = copy.deepcopy(tool.parameters)
                params.get("properties", {}).pop("user_id", None)
                if "user_id" in params.get("required", []):
                    params["required"] = [r for r in params["required"] if r != "user_id"]
                tool = tool.model_copy(update={"parameters": params})
            result.append(tool)
        return result


mcp = FastMCP(
    name="magic-sale-mcp",
    instructions=(
        "Bạn là AI bán sữa chuyên nghiệp. "
        "Dùng các tool để tìm sản phẩm, tạo đơn hàng, "
        "và quản lý thông tin cá nhân người dùng."
    ),
    middleware=[HideUserIdMiddleware()],
)


# ── Search tools ──────────────────────────────────────────────────────────


@mcp.tool()
async def search_keyword(query: str) -> list[dict]:
    """Tìm sản phẩm theo từ khoá (ILIKE). Rút gọn query thành 2-4 keyword."""
    results: list[ProductResult] = await search_keyword_impl(query)
    return [r.to_clean_dict() for r in results]


@mcp.tool()
async def rag_search(question: str, top_k: int = 3) -> list[dict]:
    """Semantic search sản phẩm bằng embedding (cosine similarity). Dùng cho nhu cầu phức tạp/triệu chứng."""
    results: list[RagResult] = await rag_search_impl(question, top_k)
    return [r.model_dump() for r in results]


@mcp.tool()
async def rag_hybrid_search(
    question: str,
    top_n: int = 5,
    use_reranker: bool = True,
    use_mmr: bool = True,
) -> list[dict]:
    """
    Advanced semantic search với hybrid vectors + reranking + diversity.

    Tốt nhất cho:
    - Nhu cầu phức tạp (triệu chứng, mô tả tình trạng)
    - Cần kết quả đa dạng (không trùng lặp brand/type)
    - Tìm kiếm theo ngữ cảnh tự nhiên

    Pipeline: Dense+Sparse search → RRF fusion → Neural reranking → MMR diversity.
    """
    results: list[RagHybridResult] = await rag_hybrid_search_impl(
        question=question,
        top_n=top_n,
        use_reranker=use_reranker,
        use_mmr=use_mmr,
    )
    return [r.model_dump() for r in results]


@mcp.tool()
async def search_by_segment(query: str) -> list[dict]:
    """Tìm sản phẩm theo đối tượng (trẻ em, người già, bà bầu, tiểu đường…). Auto-detect từ tiếng Việt."""
    results: list[ProductResult] = await search_by_segment_impl(query)
    return [r.to_clean_dict() for r in results]


@mcp.tool()
async def search_by_age(query: str) -> list[dict]:
    """Tìm sản phẩm theo độ tuổi. Auto-detect "6 tháng", "2 tuổi" từ query tiếng Việt."""
    results: list[ProductResult] = await search_by_age_impl(query)
    return [r.to_clean_dict() for r in results]


@mcp.tool()
async def list_brands() -> list[dict]:
    """Liệt kê tất cả thương hiệu sữa hiện có."""
    results: list[BrandResult] = await list_brands_impl()
    return [r.model_dump() for r in results]


@mcp.tool()
async def search_by_brand(brand_name: str) -> list[dict]:
    """Tìm sản phẩm theo thương hiệu cụ thể."""
    results: list[ProductResult] = await search_by_brand_impl(brand_name)
    return [r.to_clean_dict() for r in results]


# ── Order tool ────────────────────────────────────────────────────────────


@mcp.tool()
async def create_order(
    user_id: str,
    customer_name: str,
    customer_email: str,
    customer_phone: str,
    product_names: str = "",
    items: list[dict] | None = None,
) -> dict:
    """
    Tạo ĐƠN HÀNG DUY NHẤT với tất cả sản phẩm. CHỈ GỌI 1 LẦN cho mỗi đơn.

    Cách gọi ĐƠN GIẢN NHẤT (ưu tiên):
      create_order(product_names="Ensure Gold 800g x2, PediaSure 237ml x1", customer_name="A", customer_email="a@b.com", customer_phone="09xx")

    Cách gọi bằng items (nếu đã có UUID):
      create_order(items=[{"product_id": "uuid1", "quantity": 2}, {"product_id": "uuid2", "quantity": 1}], customer_name="A", customer_email="a@b.com", customer_phone="09xx")

    QUAN TRỌNG: Dù mua nhiều sản phẩm khác nhau, CHỈ GỌI create_order ĐÚNG 1 LẦN.
    Liệt kê TẤT CẢ sản phẩm trong product_names (phân cách bằng dấu phẩy) hoặc trong items.

    Args:
        user_id: Zalo User ID (tự động inject)
        customer_name: Tên khách hàng
        customer_email: Email khách hàng
        customer_phone: Số điện thoại khách hàng
        product_names: Tên sản phẩm, phân cách bằng dấu phẩy. Thêm "xN" cho số lượng.
                       VD: "Ensure Gold 800g x2, PediaSure 237ml x1"
        items: Danh sách sản phẩm nếu đã có UUID [{"product_id": "uuid", "quantity": int}]
    """
    import re as _re
    from app.tools.search_tool import search_keyword_impl

    # Auto-resolve product_names → items (if items not provided)
    if not items and product_names:
        items = []
        # Split by comma, parse each "product_name xN"
        for part in product_names.split(","):
            part = part.strip()
            if not part:
                continue
            # Extract quantity from "xN" or "x N" at end
            qty_match = _re.search(r'\bx\s*(\d+)\s*$', part, _re.IGNORECASE)
            if qty_match:
                qty = int(qty_match.group(1)) or 1
                name = part[:qty_match.start()].strip()
            else:
                qty = 1
                name = part
            if not name:
                continue
            search_results = await search_keyword_impl(name)
            if search_results:
                best = search_results[0]
                items.append({"product_id": best.product_id, "quantity": qty})
            else:
                return {
                    "error": True,
                    "message": f"Không tìm thấy sản phẩm '{name}' trong hệ thống."
                }

    if not items:
        return {
            "error": True,
            "message": "LỖI: Thiếu sản phẩm. Truyền product_names hoặc items."
        }

    # Auto-fix quantities
    fixed_items = []
    for item in items:
        qty = item.get("quantity", 1)
        if qty == "" or qty is None or qty == 0:
            qty = 1
        try:
            qty = int(qty)
        except (ValueError, TypeError):
            qty = 1
        fixed_items.append({"product_id": item["product_id"], "quantity": qty})

    order_items = [OrderItem(**item) for item in fixed_items]

    confirmation: OrderConfirmation = await create_order_impl(
        user_id=user_id,
        items=order_items,
        customer_name=customer_name,
        customer_email=customer_email,
        customer_phone=customer_phone,
    )
    return confirmation.model_dump()


# ── Profile tools ─────────────────────────────────────────────────────────


@mcp.tool()
async def view_personal_profile(
    user_id: str,
    file_name: Literal["USER.md", "SOUL.md", "MEMORY.md"],
) -> dict:
    """Xem nội dung file cá nhân user. BẮT BUỘC gọi trước str_replace/delete."""
    result: ProfileEditResult = await view_profile_impl(
        user_id=user_id,
        file_name=file_name,
    )
    return result.model_dump()


@mcp.tool()
async def edit_personal_profile(
    user_id: str,
    file_name: Literal["USER.md", "SOUL.md", "MEMORY.md"],
    command: Literal["str_replace", "append", "delete"],
    content: str = "",
    old_str: str | None = None,
    new_str: str | None = None,
) -> dict:
    """
    Chỉnh sửa file cá nhân user. Gọi view_personal_profile TRƯỚC.

    Commands:
      str_replace — old_str (exact match, unique) → new_str
      append      — thêm content vào cuối (chỉ cho info MỚI)
      delete      — xóa old_str khỏi file (exact match, unique)

    "xóa"/"bỏ"/"remove" = command="delete" + old_str copy từ view.
    KHÔNG BAO GIỜ dùng append để ghi chú "đã xóa X".
    """
    result: ProfileEditResult = await edit_profile_impl(
        user_id=user_id,
        file_name=file_name,
        command=command,
        content=content,
        old_str=old_str,
        new_str=new_str,
    )
    return result.model_dump()
