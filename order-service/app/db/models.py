import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Order(Base):
    __tablename__ = "orders"

    order_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    customer_name: Mapped[str] = mapped_column(Text, nullable=False)
    customer_email: Mapped[str] = mapped_column(Text, nullable=False)
    customer_phone: Mapped[str] = mapped_column(Text, nullable=False)
    # String — not Python Enum — keeps migration simple
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    total_amount: Mapped[int] = mapped_column(Numeric(14, 0), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
    )

    # Relationships
    items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",  # eager-load in every query
    )

    def __repr__(self) -> str:
        return f"<Order {self.order_id} user={self.user_id} status={self.status}>"


class OrderItem(Base):
    __tablename__ = "order_items"

    item_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("orders.order_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    product_name: Mapped[str] = mapped_column(Text, nullable=False)
    unit_price: Mapped[int] = mapped_column(Numeric(12, 0), nullable=False)
    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    # subtotal stored as plain column; computed in Python before INSERT
    subtotal: Mapped[int] = mapped_column(Numeric(14, 0), nullable=False)

    __table_args__ = (
        CheckConstraint("quantity > 0", name="order_items_quantity_positive"),
        CheckConstraint("subtotal >= 0", name="order_items_subtotal_non_negative"),
    )

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="items")

    def __repr__(self) -> str:
        return f"<OrderItem {self.item_id} product={self.product_id} qty={self.quantity}>"


class StockLedger(Base):
    __tablename__ = "stock_ledger"

    ledger_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    # Negative = sale/decrement, positive = restock/return
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    reference_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        server_default=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "reason IN ('sale','restock','adjustment','cancellation')",
            name="stock_ledger_reason_valid",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<StockLedger {self.ledger_id} product={self.product_id} "
            f"delta={self.delta} reason={self.reason}>"
        )


# ──────────────────────────────────────────────────────────────
# Lightweight table reference for cross-service UPDATE
# order-service shares the same DB as data-service, so we
# reference `products` via a minimal Table reflection object
# to avoid duplicating the full ORM model.
# ──────────────────────────────────────────────────────────────
from sqlalchemy import Table, Column, MetaData  # noqa: E402

_shared_meta = MetaData()

products_table = Table(
    "products",
    _shared_meta,
    Column("product_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("stock_quantity", Integer),
)
