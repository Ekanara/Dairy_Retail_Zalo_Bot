from __future__ import annotations

import uuid
from typing import Any

import asyncpg  # noqa: F401  — imported so exception types resolve at runtime
from sqlalchemy import String, cast, func, select, text, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.db.models import Order, OrderItem, StockLedger, products_table
from app.schemas.order import OrderCreate


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def _log(level: str, event: str, extra: dict[str, Any]) -> None:
    getattr(logger, level)(event, extra={"event": event, **extra})


# ──────────────────────────────────────────────────────────────
# Create order — FULL ACID TRANSACTION
# ──────────────────────────────────────────────────────────────

async def create_order(session: AsyncSession, data: OrderCreate) -> Order:
    """
    Single ACID transaction:
      1. INSERT orders
      2. INSERT order_items  (subtotal = unit_price * quantity)
      3. UPDATE products.stock_quantity -= quantity  (per item)
      4. INSERT stock_ledger  (delta = -quantity, reason='sale')
    """
    total_amount = sum(
        item.unit_price * item.quantity for item in data.items
    )

    try:
        async with session.begin():
            # ── 1. INSERT order ──────────────────────────────
            order = Order(
                user_id=data.user_id,
                customer_name=data.customer_name,
                customer_email=data.customer_email,
                customer_phone=data.customer_phone,
                status="pending",
                total_amount=total_amount,
            )
            session.add(order)
            await session.flush()  # populate order.order_id before items

            order_id: uuid.UUID = order.order_id

            # ── 2. INSERT order_items + stock ops per item ───
            for item_data in data.items:
                subtotal = item_data.unit_price * item_data.quantity

                # 2a. OrderItem row
                order_item = OrderItem(
                    order_id=order_id,
                    product_id=item_data.product_id,
                    product_name=item_data.product_name,
                    unit_price=item_data.unit_price,
                    quantity=item_data.quantity,
                    subtotal=subtotal,
                )
                session.add(order_item)

                # 2b. Decrement products.stock_quantity (cross-service table, same DB)
                await session.execute(
                    text(
                        "UPDATE products "
                        "SET stock_quantity = stock_quantity - :qty, "
                        "    updated_at      = now() "
                        "WHERE product_id = :pid"
                    ),
                    {"qty": item_data.quantity, "pid": str(item_data.product_id)},
                )

                # 2c. StockLedger entry
                ledger = StockLedger(
                    product_id=item_data.product_id,
                    delta=-item_data.quantity,
                    reason="sale",
                    reference_id=order_id,
                )
                session.add(ledger)

            # session.begin() context manager commits on __aexit__

        _log(
            "info",
            "order_created",
            {
                "order_id": str(order_id),
                "user_id": data.user_id,
                "item_count": len(data.items),
                "total_amount": total_amount,
            },
        )
        return order

    except IntegrityError as exc:
        _log(
            "error",
            "order_create_integrity_error",
            {
                "user_id": data.user_id,
                "error": str(exc.orig),
            },
        )
        raise
    except OperationalError as exc:
        _log(
            "error",
            "order_create_operational_error",
            {
                "user_id": data.user_id,
                "error": str(exc.orig),
            },
        )
        raise


# ──────────────────────────────────────────────────────────────
# Read helpers
# ──────────────────────────────────────────────────────────────

async def get_by_id(session: AsyncSession, order_id: uuid.UUID) -> Order | None:
    """Return Order with items eager-loaded (selectin via relationship)."""
    try:
        result = await session.execute(
            select(Order).where(Order.order_id == order_id)
        )
        order = result.scalar_one_or_none()
        return order
    except OperationalError as exc:
        _log(
            "error",
            "order_get_by_id_error",
            {"order_id": str(order_id), "error": str(exc.orig)},
        )
        raise


async def get_by_user(
    session: AsyncSession,
    user_id: str,
    page: int = 1,
    size: int = 20,
) -> tuple[list[Order], int]:
    """Return (orders, total_count) for a given user_id, paginated."""
    offset = (page - 1) * size
    try:
        count_result = await session.execute(
            select(func.count()).select_from(Order).where(Order.user_id == user_id)
        )
        total: int = count_result.scalar_one()

        orders_result = await session.execute(
            select(Order)
            .where(Order.user_id == user_id)
            .order_by(Order.created_at.desc())
            .offset(offset)
            .limit(size)
        )
        orders = list(orders_result.scalars().all())
        return orders, total
    except OperationalError as exc:
        _log(
            "error",
            "order_get_by_user_error",
            {"user_id": user_id, "error": str(exc.orig)},
        )
        raise


async def get_all(
    session: AsyncSession,
    page: int = 1,
    size: int = 20,
) -> tuple[list[Order], int]:
    """Return (orders, total_count) for admin listing, paginated."""
    offset = (page - 1) * size
    try:
        count_result = await session.execute(
            select(func.count()).select_from(Order)
        )
        total: int = count_result.scalar_one()

        orders_result = await session.execute(
            select(Order)
            .order_by(Order.created_at.desc())
            .offset(offset)
            .limit(size)
        )
        orders = list(orders_result.scalars().all())
        return orders, total
    except OperationalError as exc:
        _log(
            "error",
            "order_get_all_error",
            {"error": str(exc.orig)},
        )
        raise


# ──────────────────────────────────────────────────────────────
# Lookup by short code (first 8 chars of UUID)
# ──────────────────────────────────────────────────────────────

async def get_pending_by_short_code(
    session: AsyncSession,
    short_code: str,
) -> Order | None:
    """
    Find the most recent *pending* order whose order_id starts with
    ``short_code`` (case-insensitive).  Used by the SePay payment webhook
    to match transfer descriptions like ``DH98DC75F7``.
    """
    try:
        result = await session.execute(
            select(Order)
            .where(cast(Order.order_id, String).ilike(f"{short_code}%"))
            .where(Order.status == "pending")
            .order_by(Order.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
    except OperationalError as exc:
        _log(
            "error",
            "order_get_by_short_code_error",
            {"short_code": short_code, "error": str(exc.orig)},
        )
        raise


# ──────────────────────────────────────────────────────────────
# Update status
# ──────────────────────────────────────────────────────────────

async def update_status(
    session: AsyncSession,
    order_id: uuid.UUID,
    new_status: str,
) -> Order | None:
    """
    Update order status. If status → 'cancelled':
      - INSERT stock_ledger (delta=+quantity, reason='cancellation')
      - UPDATE products.stock_quantity += quantity
    All in a single ACID transaction.
    """
    try:
        async with session.begin():
            # Fetch order (items are selectin-loaded)
            result = await session.execute(
                select(Order).where(Order.order_id == order_id)
            )
            order = result.scalar_one_or_none()

            if order is None:
                return None

            previous_status = order.status

            # Guard: disallow re-cancelling or changing delivered orders
            if previous_status == "cancelled":
                _log(
                    "warning",
                    "order_already_cancelled",
                    {"order_id": str(order_id)},
                )
                return order

            order.status = new_status

            if new_status == "cancelled":
                for item in order.items:
                    # Restore stock
                    await session.execute(
                        text(
                            "UPDATE products "
                            "SET stock_quantity = stock_quantity + :qty, "
                            "    updated_at      = now() "
                            "WHERE product_id = :pid"
                        ),
                        {"qty": item.quantity, "pid": str(item.product_id)},
                    )

                    # Ledger entry for the reversal
                    ledger = StockLedger(
                        product_id=item.product_id,
                        delta=+item.quantity,
                        reason="cancellation",
                        reference_id=order_id,
                    )
                    session.add(ledger)

            session.add(order)

        _log(
            "info",
            "order_status_updated",
            {
                "order_id": str(order_id),
                "previous_status": previous_status,
                "new_status": new_status,
            },
        )
        return order

    except IntegrityError as exc:
        _log(
            "error",
            "order_update_status_integrity_error",
            {"order_id": str(order_id), "error": str(exc.orig)},
        )
        raise
    except OperationalError as exc:
        _log(
            "error",
            "order_update_status_operational_error",
            {"order_id": str(order_id), "error": str(exc.orig)},
        )
        raise
