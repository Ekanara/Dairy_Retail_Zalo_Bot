"""Create orders, order_items, and stock_ledger tables.

Revision ID: 001
Revises:
Create Date: 2026-03-13 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── orders ──────────────────────────────────────────────
    op.create_table(
        "orders",
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("customer_name", sa.Text, nullable=False),
        sa.Column("customer_email", sa.Text, nullable=False),
        sa.Column("customer_phone", sa.Text, nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("total_amount", sa.Numeric(14, 0), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("order_id", name="pk_orders"),
        sa.CheckConstraint(
            "status IN ('pending','confirmed','cancelled','delivered')",
            name="orders_status_valid",
        ),
    )
    op.create_index("ix_orders_user_id", "orders", ["user_id"])
    op.create_index("ix_orders_created_at", "orders", ["created_at"])

    # ── order_items ─────────────────────────────────────────
    op.create_table(
        "order_items",
        sa.Column(
            "item_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("product_name", sa.Text, nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 0), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("subtotal", sa.Numeric(14, 0), nullable=False),
        sa.PrimaryKeyConstraint("item_id", name="pk_order_items"),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.order_id"],
            name="fk_order_items_order_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("quantity > 0", name="order_items_quantity_positive"),
        sa.CheckConstraint(
            "subtotal >= 0", name="order_items_subtotal_non_negative"
        ),
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"])
    op.create_index("ix_order_items_product_id", "order_items", ["product_id"])

    # ── stock_ledger ────────────────────────────────────────
    op.create_table(
        "stock_ledger",
        sa.Column(
            "ledger_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("delta", sa.Integer, nullable=False),
        sa.Column("reason", sa.String(50), nullable=False),
        sa.Column(
            "reference_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("ledger_id", name="pk_stock_ledger"),
        sa.CheckConstraint(
            "reason IN ('sale','restock','adjustment','cancellation')",
            name="stock_ledger_reason_valid",
        ),
    )
    op.create_index("ix_stock_ledger_product_id", "stock_ledger", ["product_id"])
    op.create_index(
        "ix_stock_ledger_reference_id", "stock_ledger", ["reference_id"]
    )

    # ── auto-update updated_at trigger ──────────────────────
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_orders_updated_at
        BEFORE UPDATE ON orders
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_orders_updated_at ON orders")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column")

    op.drop_index("ix_stock_ledger_reference_id", table_name="stock_ledger")
    op.drop_index("ix_stock_ledger_product_id", table_name="stock_ledger")
    op.drop_table("stock_ledger")

    op.drop_index("ix_order_items_product_id", table_name="order_items")
    op.drop_index("ix_order_items_order_id", table_name="order_items")
    op.drop_table("order_items")

    op.drop_index("ix_orders_created_at", table_name="orders")
    op.drop_index("ix_orders_user_id", table_name="orders")
    op.drop_table("orders")
