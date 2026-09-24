"""
Data-access layer for chat_messages table.

All functions accept an `AsyncSession` (injected by the caller) so they
compose cleanly inside larger transactions when needed.

Public API
----------
create_message(session, msg_data)                → ChatMessage
get_messages_by_user(session, user_id, limit)    → list[ChatMessage]
get_messages_by_window(session, window_id, limit)→ list[ChatMessage]
get_user_id_by_window(session, window_id)        → UUID | None
delete_message(session, message_id)              → bool
"""

from __future__ import annotations

import time
import uuid

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.db.models import ChatMessage

logger = get_logger(__name__)


async def create_message(
    session: AsyncSession,
    user_id: uuid.UUID | None,
    window_id: str,
    role: str,
    content: str,
    metadata: dict | None = None,
) -> ChatMessage:
    """
    Insert a new chat message.

    Parameters
    ----------
    user_id   : Internal user UUID (can be None)
    window_id : Zalo user ID (required)
    role      : 'user', 'assistant', or 'system'
    content   : Message text
    metadata  : Optional metadata dict

    Returns
    -------
    The newly created ChatMessage row.
    """
    t0 = time.monotonic()

    msg = ChatMessage(
        user_id=user_id,
        window_id=window_id,
        role=role,
        content=content,
        meta=metadata or {},  # 'meta' is the attribute name, maps to 'metadata' column
    )
    session.add(msg)
    await session.flush()
    await session.refresh(msg)

    latency_ms = round((time.monotonic() - t0) * 1000, 2)
    logger.info(
        "chat_repo.create_message",
        message_id=str(msg.id),
        window_id=window_id,
        user_id=str(user_id) if user_id else None,
        role=role,
        latency_ms=latency_ms,
    )
    return msg


async def get_messages_by_user(
    session: AsyncSession,
    user_id: uuid.UUID,
    limit: int = 100,
) -> list[ChatMessage]:
    """
    Fetch top-K messages for a given user_id, ordered by created_at DESC.

    Returns
    -------
    List of ChatMessage objects (newest first).
    """
    t0 = time.monotonic()

    stmt = (
        select(ChatMessage)
        .where(ChatMessage.user_id == user_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    messages = list(result.scalars().all())

    latency_ms = round((time.monotonic() - t0) * 1000, 2)
    logger.info(
        "chat_repo.get_messages_by_user",
        user_id=str(user_id),
        count=len(messages),
        limit=limit,
        latency_ms=latency_ms,
    )
    return messages


async def get_messages_by_window(
    session: AsyncSession,
    window_id: str,
    limit: int = 100,
) -> list[ChatMessage]:
    """
    Fetch top-K messages for a given window_id, ordered by created_at DESC.

    Returns
    -------
    List of ChatMessage objects (newest first).
    """
    t0 = time.monotonic()

    stmt = (
        select(ChatMessage)
        .where(ChatMessage.window_id == window_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    messages = list(result.scalars().all())

    latency_ms = round((time.monotonic() - t0) * 1000, 2)
    logger.info(
        "chat_repo.get_messages_by_window",
        window_id=window_id,
        count=len(messages),
        limit=limit,
        latency_ms=latency_ms,
    )
    return messages


async def get_user_id_by_window(
    session: AsyncSession,
    window_id: str,
) -> uuid.UUID | None:
    """
    Look up the user_id associated with a window_id.

    Returns
    -------
    UUID if found (takes the first non-NULL user_id), or None.
    """
    t0 = time.monotonic()

    stmt = (
        select(ChatMessage.user_id)
        .where(ChatMessage.window_id == window_id)
        .where(ChatMessage.user_id.isnot(None))
        .limit(1)
    )
    result = await session.execute(stmt)
    user_id = result.scalar_one_or_none()

    latency_ms = round((time.monotonic() - t0) * 1000, 2)
    logger.info(
        "chat_repo.get_user_id_by_window",
        window_id=window_id,
        user_id=str(user_id) if user_id else None,
        latency_ms=latency_ms,
    )
    return user_id


async def count_messages_by_window(
    session: AsyncSession,
    window_id: str,
) -> int:
    """
    Count total messages for a given window_id.
    """
    stmt = select(func.count()).select_from(ChatMessage).where(ChatMessage.window_id == window_id)
    result = await session.execute(stmt)
    count = result.scalar_one()
    return count


async def delete_message(
    session: AsyncSession,
    message_id: uuid.UUID,
) -> bool:
    """
    Delete a chat message by ID.

    Returns
    -------
    True if deleted, False if not found.
    """
    t0 = time.monotonic()

    stmt = delete(ChatMessage).where(ChatMessage.id == message_id)
    result = await session.execute(stmt)
    await session.flush()

    deleted = result.rowcount > 0
    latency_ms = round((time.monotonic() - t0) * 1000, 2)
    logger.info(
        "chat_repo.delete_message",
        message_id=str(message_id),
        deleted=deleted,
        latency_ms=latency_ms,
    )
    return deleted
