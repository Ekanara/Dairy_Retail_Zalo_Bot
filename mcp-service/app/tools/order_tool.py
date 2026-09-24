"""
order_tool.py — MCP Tool: tạo đơn hàng qua order-service + gửi email xác nhận.
"""
import time
from typing import List
from urllib.parse import quote

import httpx
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.config import settings
from app.core.logger import get_logger
from app.db.database import get_session
from app.services.email_service import send_confirmation_email

logger = get_logger(__name__)

_TOOL_NAME = "create_order"


# --------------------------------------------------------------------------- #
# Input/Response schemas                                                      #
# --------------------------------------------------------------------------- #


class OrderItem(BaseModel):
    """Chi tiết một sản phẩm trong đơn hàng."""
    product_id: str = Field(..., description="UUID của sản phẩm")
    quantity: int = Field(..., gt=0, description="Số lượng cần đặt")


class OrderItemDetail(BaseModel):
    """Chi tiết sản phẩm đã đặt với thông tin đầy đủ."""
    product_id: str
    product_name: str
    unit_price: int
    quantity: int
    subtotal: int


class OrderConfirmation(BaseModel):
    """Kết quả trả về sau khi tạo đơn hàng thành công."""

    order_id: str
    status: str
    items: List[OrderItemDetail]
    total_amount: int
    email_sent: bool
    payment_qr_url: str = ""
    message: str


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #


async def _get_product(product_id: str) -> dict:
    """
    Lấy thông tin cơ bản của sản phẩm từ DB.

    Raises:
        ValueError: Sản phẩm không tồn tại.
        DBAPIError: Lỗi truy vấn DB.
    """
    sql = text("""
        SELECT
            product_id::text,
            name,
            price::int,
            stock_quantity
        FROM products
        WHERE product_id = :pid
    """)

    try:
        async with get_session() as session:
            result = await session.execute(sql, {"pid": product_id})
            row = result.fetchone()
    except DBAPIError as exc:
        logger.error(
            "get_product_db_error",
            extra={
                "tool_name": _TOOL_NAME,
                "product_id": product_id,
                "error": str(exc),
            },
        )
        raise

    if row is None:
        raise ValueError(f"Product '{product_id}' not found in database")

    return dict(row._mapping)


# --------------------------------------------------------------------------- #
# Tool implementation                                                          #
# --------------------------------------------------------------------------- #


async def create_order_single_product(
    user_id: str,
    product_id: str,
    quantity: int,
    customer_name: str,
    customer_email: str,
    customer_phone: str,
) -> OrderConfirmation:
    """
    Backward compatibility wrapper for single product orders.
    Converts single product order to multi-item format.
    """
    items = [OrderItem(product_id=product_id, quantity=quantity)]
    return await create_order_impl(
        user_id=user_id,
        items=items,
        customer_name=customer_name,
        customer_email=customer_email,
        customer_phone=customer_phone,
    )


async def create_order_impl(
    user_id: str,
    items: List[OrderItem],
    customer_name: str,
    customer_email: str,
    customer_phone: str,
) -> OrderConfirmation:
    """
    Tạo đơn hàng mới với nhiều sản phẩm:
      1. Lấy thông tin tất cả sản phẩm từ DB (validate còn hàng).
      2. POST tới order-service /orders (ACID: insert order + trừ stock).
      3. Gửi email xác nhận tiếng Việt cho khách.

    Args:
        user_id: Zalo User ID.
        items: Danh sách sản phẩm cần đặt (product_id và quantity).
        customer_name: Họ tên khách.
        customer_email: Email nhận xác nhận.
        customer_phone: Số điện thoại khách.

    Returns:
        OrderConfirmation chứa order_id, status, danh sách items, tổng tiền, trạng thái email.

    Raises:
        ValueError: Sản phẩm không tồn tại hoặc hết hàng.
        httpx.HTTPStatusError: order-service trả lỗi HTTP.
        httpx.RequestError: Lỗi kết nối tới order-service.
    """
    t0 = time.monotonic()

    # --- 1. Lấy thông tin tất cả sản phẩm và validate stock ---
    order_items = []
    total_amount = 0
    product_names = []

    for item in items:
        product = await _get_product(item.product_id)

        if product["stock_quantity"] < item.quantity:
            raise ValueError(
                f"Sản phẩm '{product['name']}' chỉ còn {product['stock_quantity']} "
                f"trong kho, không đủ {item.quantity} cái."
            )

        order_items.append({
            "product_id": item.product_id,
            "product_name": product["name"],
            "unit_price": product["price"],
            "quantity": item.quantity,
        })

        subtotal = product["price"] * item.quantity
        total_amount += subtotal
        product_names.append(product["name"])

    # --- 2. Tạo order qua order-service (ACID transaction nằm trong service đó) ---
    order_payload = {
        "user_id": user_id,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "customer_phone": customer_phone,
        "items": order_items,
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(
                f"{settings.ORDER_SERVICE_URL}/orders",
                json=order_payload,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "order_service_http_error",
                extra={
                    "tool_name": _TOOL_NAME,
                    "user_id": user_id,
                    "items": [{"product_id": i.product_id, "qty": i.quantity} for i in items],
                    "status_code": exc.response.status_code,
                    "response_body": exc.response.text[:200],
                },
            )
            raise
        except httpx.RequestError as exc:
            logger.error(
                "order_service_request_error",
                extra={
                    "tool_name": _TOOL_NAME,
                    "user_id": user_id,
                    "items": [{"product_id": i.product_id, "qty": i.quantity} for i in items],
                    "error": str(exc),
                },
            )
            raise

    order = resp.json()

    # --- 3. Generate VietQR payment URL ---
    order_id_short = order["order_id"][:8].upper()
    payment_qr_url = ""
    if settings.BANK_ACCOUNT_NO:
        payment_qr_url = (
            f"https://img.vietqr.io/image/{settings.BANK_BIN}-{settings.BANK_ACCOUNT_NO}"
            f"-{settings.VIETQR_TEMPLATE}.png"
            f"?amount={total_amount}"
            f"&addInfo={quote(f'DH{order_id_short}')}"
            f"&accountName={quote(settings.BANK_ACCOUNT_NAME)}"
        )

    # --- 3b. Send QR image to customer via Zalo (fire-and-forget) ---
    if payment_qr_url:
        try:
            async with httpx.AsyncClient(timeout=10.0) as zalo_http:
                await zalo_http.post(
                    f"{settings.ZALO_SERVICE_URL}/internal/send-photo",
                    json={
                        "user_id": user_id,
                        "image_url": payment_qr_url,
                        "caption": f"Ma QR thanh toan don #{order_id_short} - {total_amount:,}d",
                    },
                )
            logger.info("qr_photo_sent", extra={"order_id": order["order_id"], "user_id": user_id})
        except Exception as exc:
            logger.error("qr_photo_send_failed", extra={"error": str(exc), "order_id": order["order_id"]})

    # --- 4. Email gửi SAU KHI thanh toán (qua SePay webhook → order-service) ---
    # KHÔNG gửi email ở đây. Chờ SePay xác nhận đã nhận đủ tiền.
    email_sent = False

    # --- 5. Prepare response ---
    order_item_details = []
    for item in order_items:
        order_item_details.append(OrderItemDetail(
            product_id=item["product_id"],
            product_name=item["product_name"],
            unit_price=item["unit_price"],
            quantity=item["quantity"],
            subtotal=item["unit_price"] * item["quantity"],
        ))

    duration_ms = round((time.monotonic() - t0) * 1000, 2)

    logger.info(
        "create_order_done",
        extra={
            "tool_name": _TOOL_NAME,
            "user_id": user_id,
            "order_id": order["order_id"],
            "item_count": len(items),
            "total_amount": total_amount,
            "email_sent": email_sent,
            "duration_ms": duration_ms,
        },
    )

    # Tạo summary message với danh sách sản phẩm
    if len(product_names) == 1:
        products_summary = product_names[0]
    elif len(product_names) == 2:
        products_summary = f"{product_names[0]} và {product_names[1]}"
    else:
        products_summary = f"{', '.join(product_names[:-1])}, và {product_names[-1]}"

    return OrderConfirmation(
        order_id=order["order_id"],
        status=order["status"],
        items=order_item_details,
        total_amount=total_amount,
        email_sent=email_sent,
        payment_qr_url=payment_qr_url,
        message=(
            f"Đơn hàng #{order_id_short} ({len(items)} sản phẩm: {products_summary}) đã được tạo thành công!"
            + f"\nTổng thanh toán: {total_amount:,}đ."
            + (f"\nMã QR thanh toán đã gửi qua Zalo. Khách vui lòng chuyển khoản theo QR, nội dung: DH{order_id_short}." if payment_qr_url else "")
            + "\nEmail xác nhận sẽ được gửi SAU KHI nhận đủ thanh toán."
        ),
    )


# Helper function to handle multi-item email
async def send_confirmation_email_multi_items(
    to_email: str,
    customer_name: str,
    order_items: List[dict],
    total_amount: int,
    payment_qr_url: str = "",
) -> bool:
    """
    Gửi email xác nhận cho đơn hàng nhiều sản phẩm.
    Sử dụng template email mới hỗ trợ hiển thị nhiều sản phẩm.
    """
    from app.services.email_service import send_confirmation_email_multi
    return await send_confirmation_email_multi(
        to_email=to_email,
        customer_name=customer_name,
        order_items=order_items,
        total_amount=total_amount,
        payment_qr_url=payment_qr_url,
    )
