from __future__ import annotations

import asyncio
import re
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logger import logger
from app.db.database import get_db_session
from app.repositories import order_repo
from app.schemas.order import (
    OrderCreate,
    OrderListResponse,
    OrderRead,
    OrderStatusUpdate,
)
from app.services import order_service
from app.services.order_service import (
    InvalidStatusTransitionError,
    OrderNotFoundError,
)

router = APIRouter()


# ──────────────────────────────────────────────────────────────
# Health check
# ──────────────────────────────────────────────────────────────

@router.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "order-service"}


# ──────────────────────────────────────────────────────────────
# POST /webhook/sepay — SePay payment notification
# ──────────────────────────────────────────────────────────────

_ORDER_CODE_RE = re.compile(r"DH([A-F0-9]{8})", re.IGNORECASE)


async def _notify_zalo(user_id: str, text: str) -> None:
    """Fire-and-forget: send a Zalo message via zalo-service."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{settings.ZALO_SERVICE_URL}/internal/send-message",
                json={"user_id": user_id, "text": text},
            )
    except Exception as exc:
        logger.error(
            "Failed to send Zalo payment notification",
            extra={"event": "zalo_notify_failed", "user_id": user_id, "error": str(exc)},
        )


async def _send_payment_email(order, transfer_amount: int) -> None:
    """Fire-and-forget: send payment confirmation email."""
    try:
        from app.services.email_service import send_payment_confirmation
        await send_payment_confirmation(order, transfer_amount)
    except Exception as exc:
        logger.error(
            "Failed to send payment email",
            extra={"event": "payment_email_task_failed", "error": str(exc)},
        )


@router.post("/webhook/sepay", tags=["webhooks"])
async def sepay_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Receive payment notifications from SePay.

    Flow:
      1. Verify API key (if configured)
      2. Extract order code (DH{8 hex chars}) from transfer content
      3. Find matching pending order
      4. Verify amount >= order total
      5. Update order status → confirmed
      6. Send thank-you message to customer via Zalo
    """
    # --- 1. Verify API key ---
    if settings.SEPAY_API_KEY:
        auth_header = request.headers.get("Authorization", "")
        expected = f"Apikey {settings.SEPAY_API_KEY}"
        if auth_header != expected:
            logger.warning(
                "SePay webhook auth failed",
                extra={"event": "sepay_auth_failed"},
            )
            raise HTTPException(status_code=403, detail="Invalid API key")

    # --- 2. Parse payload ---
    body = await request.json()
    content = body.get("content", "")
    transfer_amount = body.get("transferAmount", 0)
    transfer_type = body.get("transferType", "")
    transaction_id = body.get("id", "")
    reference_code = body.get("referenceCode", "")

    logger.info(
        "SePay webhook received",
        extra={
            "event": "sepay_webhook_received",
            "transaction_id": transaction_id,
            "transfer_type": transfer_type,
            "transfer_amount": transfer_amount,
            "content": content[:100],
        },
    )

    # Only process incoming transfers
    if transfer_type != "in":
        return {"success": True, "message": "ignored (not incoming)"}

    # --- 3. Extract order code ---
    match = _ORDER_CODE_RE.search(content.upper())
    if not match:
        logger.info(
            "SePay webhook: no order code found",
            extra={"event": "sepay_no_order_code", "content": content[:100]},
        )
        return {"success": True, "message": "no order code found"}

    short_code = match.group(1).lower()

    # --- 4. Find pending order ---
    order = await order_repo.get_pending_by_short_code(session, short_code)

    if order is None:
        logger.info(
            "SePay webhook: no pending order for code",
            extra={"event": "sepay_order_not_found", "short_code": short_code},
        )
        return {"success": True, "message": f"no pending order for DH{short_code.upper()}"}

    # --- 5. Verify amount ---
    order_total = int(order.total_amount)
    if transfer_amount < order_total:
        logger.warning(
            "SePay webhook: amount mismatch",
            extra={
                "event": "sepay_amount_mismatch",
                "order_id": str(order.order_id),
                "expected": order_total,
                "received": transfer_amount,
            },
        )
        return {
            "success": True,
            "message": f"amount {transfer_amount} < order total {order_total}",
        }

    # --- 6. Confirm order (direct update, no nested transaction) ---
    order_id = order.order_id
    user_id = order.user_id
    order.status = "confirmed"
    session.add(order)
    await session.commit()

    logger.info(
        "SePay webhook: order confirmed",
        extra={
            "event": "sepay_order_confirmed",
            "order_id": str(order_id),
            "transfer_amount": transfer_amount,
            "reference_code": reference_code,
        },
    )

    # --- 7. Notify customer via Zalo + Email (fire-and-forget) ---
    order_id_short = str(order_id)[:8].upper()
    thank_you = (
        f"Cảm ơn bạn đã thanh toán đơn hàng #{order_id_short}! "
        f"Chúng tôi đã nhận được {transfer_amount:,.0f}đ. "
        f"Đơn hàng của bạn đang được xử lý."
    )
    asyncio.create_task(_notify_zalo(user_id, thank_you))
    asyncio.create_task(_send_payment_email(order, transfer_amount))

    return {"success": True, "message": f"order {order_id_short} confirmed"}


# ──────────────────────────────────────────────────────────────
# POST /orders — create new order
# ──────────────────────────────────────────────────────────────

@router.post(
    "/orders",
    response_model=OrderRead,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo đơn hàng mới",
    tags=["orders"],
)
async def create_order(
    payload: OrderCreate,
    session: AsyncSession = Depends(get_db_session),
) -> OrderRead:
    try:
        return await order_service.create_order(session, payload)
    except Exception as exc:
        logger.error(
            "POST /orders failed",
            extra={"event": "route_create_order_error", "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


# ──────────────────────────────────────────────────────────────
# GET /orders — admin list (must be registered BEFORE /{order_id})
# ──────────────────────────────────────────────────────────────

@router.get(
    "/orders",
    response_model=OrderListResponse,
    summary="[Admin] Danh sách tất cả đơn hàng",
    tags=["orders"],
)
async def list_all_orders(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
) -> OrderListResponse:
    try:
        return await order_service.get_all_orders(session, page, size)
    except Exception as exc:
        logger.error(
            "GET /orders failed",
            extra={"event": "route_list_orders_error", "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve orders",
        ) from exc


# ──────────────────────────────────────────────────────────────
# GET /orders/user/{user_id} — order history for a Zalo user
# (registered BEFORE /{order_id} to avoid ambiguity)
# ──────────────────────────────────────────────────────────────

@router.get(
    "/orders/user/{user_id}",
    response_model=OrderListResponse,
    summary="Lịch sử đơn hàng của một user",
    tags=["orders"],
)
async def list_user_orders(
    user_id: str,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
) -> OrderListResponse:
    try:
        return await order_service.get_orders_by_user(session, user_id, page, size)
    except Exception as exc:
        logger.error(
            "GET /orders/user/{user_id} failed",
            extra={
                "event": "route_list_user_orders_error",
                "user_id": user_id,
                "error": str(exc),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user orders",
        ) from exc


# ──────────────────────────────────────────────────────────────
# GET /orders/{order_id} — single order detail
# ──────────────────────────────────────────────────────────────

@router.get(
    "/orders/{order_id}",
    response_model=OrderRead,
    summary="Chi tiết một đơn hàng",
    tags=["orders"],
)
async def get_order(
    order_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> OrderRead:
    try:
        return await order_service.get_order(session, order_id)
    except OrderNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error(
            "GET /orders/{order_id} failed",
            extra={
                "event": "route_get_order_error",
                "order_id": str(order_id),
                "error": str(exc),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve order",
        ) from exc


# ──────────────────────────────────────────────────────────────
# PATCH /orders/{order_id}/status
# ──────────────────────────────────────────────────────────────

@router.patch(
    "/orders/{order_id}/status",
    response_model=OrderRead,
    summary="Cập nhật trạng thái đơn hàng",
    tags=["orders"],
)
async def update_order_status(
    order_id: uuid.UUID,
    payload: OrderStatusUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> OrderRead:
    try:
        return await order_service.update_order_status(session, order_id, payload)
    except OrderNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error(
            "PATCH /orders/{order_id}/status failed",
            extra={
                "event": "route_update_status_error",
                "order_id": str(order_id),
                "error": str(exc),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update order status",
        ) from exc
