from __future__ import annotations

import asyncio
import time
import uuid

from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.db.models import Order
from app.repositories import order_repo
from app.schemas.order import (
    OrderCreate,
    OrderListResponse,
    OrderRead,
    OrderStatusUpdate,
)


def _ms(start: float) -> int:
    return round((time.monotonic() - start) * 1000)


class OrderNotFoundError(Exception):
    """Raised when the requested order does not exist."""


class OrderAlreadyCancelledError(Exception):
    """Raised when attempting to modify an already-cancelled order."""


class InvalidStatusTransitionError(Exception):
    """Raised when the requested status transition is not allowed."""


# ──────────────────────────────────────────────────────────────
# Create
# ──────────────────────────────────────────────────────────────

async def create_order(session: AsyncSession, data: OrderCreate) -> OrderRead:
    start = time.monotonic()
    logger.info(
        "Creating order",
        extra={
            "event": "order_create_start",
            "user_id": data.user_id,
            "item_count": len(data.items),
        },
    )

    try:
        created: Order = await order_repo.create_order(session, data)
        order = await order_repo.get_by_id(session, created.order_id)
    except IntegrityError as exc:
        logger.error(
            "Order creation failed — integrity constraint",
            extra={
                "event": "order_create_failed",
                "user_id": data.user_id,
                "error": str(exc.orig),
                "latency_ms": _ms(start),
            },
        )
        raise
    except OperationalError as exc:
        logger.error(
            "Order creation failed — operational error",
            extra={
                "event": "order_create_failed",
                "user_id": data.user_id,
                "error": str(exc.orig),
                "latency_ms": _ms(start),
            },
        )
        raise

    if order is None:
        raise OrderNotFoundError("Order created but could not be reloaded")

    latency = _ms(start)
    logger.info(
        "Order created successfully",
        extra={
            "event": "order_create_success",
            "order_id": str(order.order_id),
            "user_id": data.user_id,
            "total_amount": int(order.total_amount),
            "latency_ms": latency,
        },
    )
    result = OrderRead.model_validate(order)
    asyncio.create_task(_send_email_safe(result))
    return result


async def _send_email_safe(order: OrderRead) -> None:
    """Fire-and-forget email wrapper. Never raises."""
    try:
        from app.services.email_service import send_order_confirmation
        await send_order_confirmation(order)
    except Exception as exc:
        logger.error(
            "Email task failed unexpectedly",
            extra={"event": "email_task_error", "order_id": str(order.order_id), "error": str(exc)},
        )


# ──────────────────────────────────────────────────────────────
# Read single
# ──────────────────────────────────────────────────────────────

async def get_order(session: AsyncSession, order_id: uuid.UUID) -> OrderRead:
    start = time.monotonic()

    try:
        order = await order_repo.get_by_id(session, order_id)
    except OperationalError as exc:
        logger.error(
            "Failed to fetch order",
            extra={
                "event": "order_fetch_failed",
                "order_id": str(order_id),
                "error": str(exc.orig),
                "latency_ms": _ms(start),
            },
        )
        raise

    if order is None:
        logger.warning(
            "Order not found",
            extra={
                "event": "order_not_found",
                "order_id": str(order_id),
                "latency_ms": _ms(start),
            },
        )
        raise OrderNotFoundError(f"Order {order_id} not found")

    return OrderRead.model_validate(order)


# ──────────────────────────────────────────────────────────────
# Read by user
# ──────────────────────────────────────────────────────────────

async def get_orders_by_user(
    session: AsyncSession,
    user_id: str,
    page: int,
    size: int,
) -> OrderListResponse:
    start = time.monotonic()

    try:
        orders, total = await order_repo.get_by_user(session, user_id, page, size)
    except OperationalError as exc:
        logger.error(
            "Failed to fetch user orders",
            extra={
                "event": "order_fetch_user_failed",
                "user_id": user_id,
                "error": str(exc.orig),
                "latency_ms": _ms(start),
            },
        )
        raise

    logger.info(
        "User orders fetched",
        extra={
            "event": "order_fetch_user_success",
            "user_id": user_id,
            "total": total,
            "page": page,
            "size": size,
            "latency_ms": _ms(start),
        },
    )
    return OrderListResponse(
        items=[OrderRead.model_validate(o) for o in orders],
        total=total,
        page=page,
        size=size,
    )


# ──────────────────────────────────────────────────────────────
# Read all (admin)
# ──────────────────────────────────────────────────────────────

async def get_all_orders(
    session: AsyncSession,
    page: int,
    size: int,
) -> OrderListResponse:
    start = time.monotonic()

    try:
        orders, total = await order_repo.get_all(session, page, size)
    except OperationalError as exc:
        logger.error(
            "Failed to fetch all orders",
            extra={
                "event": "order_fetch_all_failed",
                "error": str(exc.orig),
                "latency_ms": _ms(start),
            },
        )
        raise

    logger.info(
        "All orders fetched",
        extra={
            "event": "order_fetch_all_success",
            "total": total,
            "page": page,
            "size": size,
            "latency_ms": _ms(start),
        },
    )
    return OrderListResponse(
        items=[OrderRead.model_validate(o) for o in orders],
        total=total,
        page=page,
        size=size,
    )


# ──────────────────────────────────────────────────────────────
# Update status
# ──────────────────────────────────────────────────────────────

_VALID_TRANSITIONS: dict[str, set[str]] = {
    "pending":   {"confirmed", "cancelled"},
    "confirmed": {"delivered", "cancelled"},
    "delivered": set(),       # terminal
    "cancelled": set(),       # terminal
}


async def update_order_status(
    session: AsyncSession,
    order_id: uuid.UUID,
    payload: OrderStatusUpdate,
) -> OrderRead:
    start = time.monotonic()
    new_status = payload.status

    # Pre-fetch to validate transition before entering the transaction
    try:
        existing = await order_repo.get_by_id(session, order_id)
    except OperationalError as exc:
        logger.error(
            "Failed to fetch order for status update",
            extra={
                "event": "order_status_prefetch_failed",
                "order_id": str(order_id),
                "error": str(exc.orig),
            },
        )
        raise

    if existing is None:
        raise OrderNotFoundError(f"Order {order_id} not found")

    allowed = _VALID_TRANSITIONS.get(existing.status, set())
    if new_status not in allowed:
        raise InvalidStatusTransitionError(
            f"Cannot transition from '{existing.status}' to '{new_status}'"
        )

    try:
        order = await order_repo.update_status(session, order_id, new_status)
    except (IntegrityError, OperationalError) as exc:
        logger.error(
            "Order status update failed",
            extra={
                "event": "order_status_update_failed",
                "order_id": str(order_id),
                "new_status": new_status,
                "error": str(exc.orig),
                "latency_ms": _ms(start),
            },
        )
        raise

    if order is None:
        raise OrderNotFoundError(f"Order {order_id} not found")

    logger.info(
        "Order status updated",
        extra={
            "event": "order_status_update_success",
            "order_id": str(order_id),
            "new_status": new_status,
            "latency_ms": _ms(start),
        },
    )
    return OrderRead.model_validate(order)
