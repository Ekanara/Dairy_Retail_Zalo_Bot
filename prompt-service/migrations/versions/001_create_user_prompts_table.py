"""Create user_prompts table

Revision ID: 001
Revises:
Create Date: 2026-03-13 00:00:00.000000

Schema
------
    user_prompts
    ├── id          UUID PK  default gen_random_uuid()
    ├── user_id     VARCHAR(255)  UNIQUE NOT NULL
    ├── soul_md     TEXT  DEFAULT ''
    ├── user_md     TEXT  DEFAULT ''
    ├── memory_md   TEXT  DEFAULT ''
    ├── created_at  TIMESTAMPTZ  DEFAULT now()
    └── updated_at  TIMESTAMPTZ  DEFAULT now()

Notes
-----
- `pgcrypto` extension is enabled for gen_random_uuid() on PostgreSQL < 13.
  PostgreSQL 13+ has gen_random_uuid() built-in; the CREATE EXTENSION is
  guarded with IF NOT EXISTS so it is safe to run on any version.
- An index on `user_id` is created separately for fast lookup by Zalo ID.
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
    # Enable pgcrypto so gen_random_uuid() is available on PG < 13
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "user_prompts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Surrogate PK — never exposed to callers",
        ),
        sa.Column(
            "user_id",
            sa.String(length=255),
            nullable=False,
            comment="Zalo user_id — natural key used in all API routes",
        ),
        sa.Column(
            "soul_md",
            sa.Text(),
            nullable=False,
            server_default="",
            comment="Per-user SOUL.md content (tone, personality overrides)",
        ),
        sa.Column(
            "user_md",
            sa.Text(),
            nullable=False,
            server_default="",
            comment="Per-user USER.md content (name, preferred brands, history)",
        ),
        sa.Column(
            "memory_md",
            sa.Text(),
            nullable=False,
            server_default="",
            comment="Per-user MEMORY.md content (sales patterns, anti-patterns)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # ── constraints ───────────────────────────────────────────────────────
        sa.UniqueConstraint("user_id", name="uq_user_prompts_user_id"),
        sa.CheckConstraint("char_length(user_id) > 0", name="ck_user_prompts_user_id_nonempty"),
    )

    # Explicit B-tree index on user_id for O(log n) lookups
    op.create_index(
        "ix_user_prompts_user_id",
        "user_prompts",
        ["user_id"],
        unique=True,
    )

    # Trigger to auto-update updated_at on every row change ───────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_user_prompts_updated_at
        BEFORE UPDATE ON user_prompts
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_user_prompts_updated_at ON user_prompts")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column")
    op.drop_index("ix_user_prompts_user_id", table_name="user_prompts")
    op.drop_table("user_prompts")
