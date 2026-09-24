"""
ORM models for chat-service.

Schema
------
chat_messages table:
    id           UUID  PK  default gen_random_uuid()
    user_id      UUID  NULLABLE  — internal user UUID
    window_id    VARCHAR(255)  NOT NULL  — Zalo user ID
    role         VARCHAR(50)  NOT NULL  — 'user' | 'assistant' | 'system'
    content      TEXT  NOT NULL
    metadata     JSONB  DEFAULT '{}'  — extensible metadata (tool_calls, etc.)
    created_at   TIMESTAMPTZ  DEFAULT now()

Indexes:
    - (user_id, created_at DESC)  — fast top-K by user_id
    - (window_id, created_at DESC)  — fast top-K by window_id
    - (window_id)  — fast user_id lookup
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
        comment="Primary key — unique message ID",
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="Internal user UUID — can be NULL if only window_id is known",
    )
    window_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Zalo user ID — always present",
    )
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Message role: 'user', 'assistant', or 'system'",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Message text content",
    )
    meta: Mapped[dict] = mapped_column(
        "metadata",  # Column name in DB
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Extensible metadata (tool_calls, model_name, etc.)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
        index=True,
        comment="Message creation timestamp",
    )

    # Composite indexes for fast top-K queries
    __table_args__ = (
        Index(
            "ix_chat_messages_user_id_created_at",
            "user_id",
            created_at.desc(),
        ),
        Index(
            "ix_chat_messages_window_id_created_at",
            "window_id",
            created_at.desc(),
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<ChatMessage id={self.id} window_id={self.window_id!r} "
            f"role={self.role!r} created_at={self.created_at.isoformat()}>"
        )
