"""001_create_products_table

Revision ID: 001
Revises:
Create Date: 2026-03-13 00:00:00.000000

Creates the `products` table with:
  - UUID primary key (gen_random_uuid)
  - All product catalog columns
  - stock_quantity with DEFAULT 100
  - Audit timestamps with DEFAULT now()
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------
revision: str = "001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Enable pgcrypto so gen_random_uuid() is available
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "products",
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.TEXT(), nullable=False),
        sa.Column("brand", sa.VARCHAR(length=100), nullable=True),
        sa.Column("origin", sa.VARCHAR(length=100), nullable=True),
        sa.Column("customer_segment", sa.TEXT(), nullable=True),
        sa.Column("product_purpose", sa.TEXT(), nullable=True),
        sa.Column("how_use", sa.TEXT(), nullable=True),
        sa.Column("price", sa.NUMERIC(precision=12, scale=0), nullable=True),
        sa.Column(
            "stock_quantity",
            sa.INTEGER(),
            nullable=False,
            server_default=sa.text("100"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Index on brand for fast filter queries
    op.create_index("ix_products_brand", "products", ["brand"])
    # Index on customer_segment for filter queries
    op.create_index("ix_products_customer_segment", "products", ["customer_segment"])
    # Index on stock_quantity for in-stock / out-of-stock queries
    op.create_index("ix_products_stock_quantity", "products", ["stock_quantity"])


def downgrade() -> None:
    op.drop_index("ix_products_stock_quantity", table_name="products")
    op.drop_index("ix_products_customer_segment", table_name="products")
    op.drop_index("ix_products_brand", table_name="products")
    op.drop_table("products")
