"""
ORM model for the `user_prompts` table.

Schema
------
    id          UUID  PK  default gen_random_uuid()
    user_id     VARCHAR(255)  UNIQUE  NOT NULL
    soul_md     TEXT  DEFAULT ''
    user_md     TEXT  DEFAULT ''
    memory_md   TEXT  DEFAULT ''
    created_at  TIMESTAMPTZ  DEFAULT now()
    updated_at  TIMESTAMPTZ  DEFAULT now()

The `updated_at` column is maintained automatically by a SQLAlchemy
`onupdate` hook so every `session.flush()` refreshes the timestamp.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class UserPrompt(Base):
    __tablename__ = "user_prompts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
        comment="Surrogate PK — never exposed to callers",
    )
    user_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Zalo user_id — natural key used in all API routes",
    )
    soul_md: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        server_default="",
        comment="Per-user SOUL.md content (tone, personality overrides)",
    )
    user_md: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        server_default="",
        comment="Per-user USER.md content (name, preferred brands, history)",
    )
    memory_md: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        server_default="",
        comment="Per-user MEMORY.md content (sales patterns, anti-patterns)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<UserPrompt user_id={self.user_id!r} "
            f"updated_at={self.updated_at.isoformat()}>"
        )
