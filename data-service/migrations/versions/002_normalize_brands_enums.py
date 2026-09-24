"""002_normalize_brands_enums

Revision ID: 002
Revises: 001
Create Date: 2026-03-18 00:00:00.000000

Normalizes the products table:
  - Creates customer_segment, customer_age, and product_origin ENUMs
  - Extracts brands into a dedicated `brands` table (seeded with Abbott brands)
  - Replaces the text `brand` column with a FK `brand_id` to `brands`
  - Converts customer_segment and origin columns to ENUM types
  - Adds a new customer_age ENUM column
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------
revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | None = None
depends_on: str | None = None

# ---------------------------------------------------------------------------
# ENUM definitions (kept here so upgrade/downgrade can reference them)
# ---------------------------------------------------------------------------
CUSTOMER_SEGMENT_VALUES = (
    "children", "elderly", "women", "patients", "breastfeeding_mothers",
    "pregnant_mothers", "diabetic", "general",
)

CUSTOMER_AGE_VALUES = (
    "age_0m_6m", "age_6m_36m", "age_4y_12y", "age_13y_17y",
    "age_18y_40y", "age_41y_60y", "age_60y_plus", "all_ages",
)

PRODUCT_ORIGIN_VALUES = (
    "usa", "ireland", "singapore", "vietnam",
)

ABBOTT_BRANDS = (
    "Ensure", "Glucerna", "PediaSure", "Similac", "Abbott Grow", "Similac Mom",
)


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Create ENUM types
    # ------------------------------------------------------------------
    op.execute(
        "CREATE TYPE customer_segment AS ENUM ("
        + ", ".join(f"'{v}'" for v in CUSTOMER_SEGMENT_VALUES)
        + ")"
    )
    op.execute(
        "CREATE TYPE customer_age AS ENUM ("
        + ", ".join(f"'{v}'" for v in CUSTOMER_AGE_VALUES)
        + ")"
    )
    op.execute(
        "CREATE TYPE product_origin AS ENUM ("
        + ", ".join(f"'{v}'" for v in PRODUCT_ORIGIN_VALUES)
        + ")"
    )

    # ------------------------------------------------------------------
    # 2. Create `brands` table and seed with Abbott brands
    # ------------------------------------------------------------------
    op.create_table(
        "brands",
        sa.Column(
            "brand_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.VARCHAR(length=100), nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Seed the six Abbott brands
    for brand in ABBOTT_BRANDS:
        op.execute(
            f"INSERT INTO brands (name) VALUES ('{brand}')"
        )

    # ------------------------------------------------------------------
    # 3. Alter `products` table
    # ------------------------------------------------------------------

    # 3a. Add brand_id FK column
    op.add_column(
        "products",
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_products_brand_id",
        "products",
        "brands",
        ["brand_id"],
        ["brand_id"],
        ondelete="SET NULL",
    )

    # 3b. Back-fill brand_id from the existing text `brand` column
    op.execute(
        "UPDATE products "
        "SET brand_id = brands.brand_id "
        "FROM brands "
        "WHERE LOWER(products.brand) = LOWER(brands.name)"
    )

    # 3c. Drop the old text `brand` column (and its index)
    op.drop_index("ix_products_brand", table_name="products")
    op.drop_column("products", "brand")

    # 3d. Convert customer_segment from TEXT to the new ENUM
    op.execute(
        "ALTER TABLE products "
        "ALTER COLUMN customer_segment TYPE customer_segment "
        "USING customer_segment::customer_segment"
    )

    # 3e. Add new customer_age column (nullable)
    op.add_column(
        "products",
        sa.Column(
            "customer_age",
            postgresql.ENUM(*CUSTOMER_AGE_VALUES, name="customer_age", create_type=False),
            nullable=True,
        ),
    )

    # 3f. Convert origin from VARCHAR to product_origin ENUM (lowercase)
    op.execute(
        "ALTER TABLE products "
        "ALTER COLUMN origin TYPE product_origin "
        "USING LOWER(origin)::product_origin"
    )

    # 3g. Create index on brand_id
    op.create_index("ix_products_brand_id", "products", ["brand_id"])


def downgrade() -> None:
    # ------------------------------------------------------------------
    # Reverse all changes in opposite order
    # ------------------------------------------------------------------

    # Drop brand_id index
    op.drop_index("ix_products_brand_id", table_name="products")

    # Convert origin back to VARCHAR(100)
    op.execute(
        "ALTER TABLE products "
        "ALTER COLUMN origin TYPE VARCHAR(100) "
        "USING origin::TEXT"
    )

    # Drop customer_age column
    op.drop_column("products", "customer_age")

    # Convert customer_segment back to TEXT
    op.execute(
        "ALTER TABLE products "
        "ALTER COLUMN customer_segment TYPE TEXT "
        "USING customer_segment::TEXT"
    )

    # Re-add the old text `brand` column
    op.add_column(
        "products",
        sa.Column("brand", sa.VARCHAR(length=100), nullable=True),
    )

    # Back-fill brand name from brands table
    op.execute(
        "UPDATE products "
        "SET brand = brands.name "
        "FROM brands "
        "WHERE products.brand_id = brands.brand_id"
    )

    # Recreate original brand index
    op.create_index("ix_products_brand", "products", ["brand"])

    # Drop FK and brand_id column
    op.drop_constraint("fk_products_brand_id", "products", type_="foreignkey")
    op.drop_column("products", "brand_id")

    # Drop brands table
    op.drop_table("brands")

    # Drop ENUM types
    op.execute("DROP TYPE IF EXISTS product_origin")
    op.execute("DROP TYPE IF EXISTS customer_age")
    op.execute("DROP TYPE IF EXISTS customer_segment")
