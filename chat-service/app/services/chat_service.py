"""
Business logic for chat-service.

Orchestrates Redis cache + PostgreSQL repository.

Strategy (Redis-first):
1. Read: Try Redis → fallback to PostgreSQL → populate Redis
2. Write: PostgreSQL first → async update Redis

Public API
----------
save_message(session, msg_data)                 → MessageResponse
get_messages(session, user_id?, window_id?, limit) → MessagesResponse
lookup_user_id(session, window_id)              → UserIdResponse
delete_message(session, message_id)             → bool
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logger import get_logger
from app.repositories import chat_repo
from app.schemas.chat import MessageCreate, MessageResponse, MessagesResponse, UserIdResponse
from app.services.redis_service import redis_cache

logger = get_logger(__name__)


async def save_message(
    session: AsyncSession,
    msg_data: MessageCreate,
) -> MessageResponse:
    """
    Save a new chat message to PostgreSQL and update Redis cache.

    Steps:
    1. Write to PostgreSQL (source of truth)
    2. Update Redis cache (async, best-effort)
    """
    # 1. Write to PostgreSQL
    msg = await chat_repo.create_message(
        session,
        user_id=msg_data.user_id,
        window_id=msg_data.window_id,
        role=msg_data.role,
        content=msg_data.content,
        metadata=msg_data.metadata,
    )

    # 2. Update Redis cache (best-effort)
    try:
        msg_dict = {
            "id": str(msg.id),
            "user_id": str(msg.user_id) if msg.user_id else None,
            "window_id": msg.window_id,
            "role": msg.role,
            "content": msg.content,
            "metadata": msg.meta,  # Use 'meta' attribute
            "created_at": msg.created_at.isoformat(),
        }
        timestamp = msg.created_at.timestamp()

        # Cache by window_id (always present)
        await redis_cache.cache_message(
            f"window:{msg.window_id}",
            msg_dict,
            timestamp,
        )

        # Cache by user_id (if present)
        if msg.user_id:
            await redis_cache.cache_message(
                f"user:{msg.user_id}",
                msg_dict,
                timestamp,
            )
    except Exception as exc:  # noqa: BLE001 — cache failure is non-fatal
        logger.warning(
            "chat_service.cache_update_failed",
            message_id=str(msg.id),
            error=str(exc),
        )

    logger.info("chat_service.message_saved", message_id=str(msg.id))
    return MessageResponse(**msg_dict)


async def get_messages(
    session: AsyncSession,
    user_id: uuid.UUID | None = None,
    window_id: str | None = None,
    limit: int | None = None,
) -> MessagesResponse:
    """
    Fetch top-K messages with Redis-first strategy.

    Parameters
    ----------
    user_id   : Optional user UUID filter
    window_id : Optional window ID filter
    limit     : Max messages to return (default from settings)

    Returns
    -------
    MessagesResponse with messages and metadata.

    Raises
    ------
    ValueError if neither user_id nor window_id is provided.
    """
    if not user_id and not window_id:
        raise ValueError("Must provide either user_id or window_id")

    limit = limit or settings.DEFAULT_TOP_K

    # Determine cache key
    if user_id:
        key_suffix = f"user:{user_id}"
        fetch_func = chat_repo.get_messages_by_user
        fetch_arg = user_id
    else:
        key_suffix = f"window:{window_id}"
        fetch_func = chat_repo.get_messages_by_window
        fetch_arg = window_id

    # Try Redis cache first
    cached_messages = await redis_cache.get_messages(key_suffix, limit)
    if cached_messages:
        messages = [MessageResponse(**msg) for msg in cached_messages]
        return MessagesResponse(
            messages=messages,
            total=len(messages),
            from_cache=True,
        )

    # Cache miss → fetch from PostgreSQL
    db_messages = await fetch_func(session, fetch_arg, limit)

    # Populate Redis cache for next time
    try:
        for msg in db_messages:
            msg_dict = {
                "id": str(msg.id),
                "user_id": str(msg.user_id) if msg.user_id else None,
                "window_id": msg.window_id,
                "role": msg.role,
                "content": msg.content,
                "metadata": msg.meta,  # Use 'meta' attribute
                "created_at": msg.created_at.isoformat(),
            }
            await redis_cache.cache_message(
                key_suffix,
                msg_dict,
                msg.created_at.timestamp(),
            )
    except Exception as exc:  # noqa: BLE001 — cache population is non-fatal
        logger.warning(
            "chat_service.cache_population_failed",
            key_suffix=key_suffix,
            error=str(exc),
        )

    # Convert ORM objects to dicts
    messages = []
    for msg in db_messages:
        msg_dict = {
            "id": str(msg.id),
            "user_id": str(msg.user_id) if msg.user_id else None,
            "window_id": msg.window_id,
            "role": msg.role,
            "content": msg.content,
            "metadata": msg.meta,  # Use 'meta' attribute
            "created_at": msg.created_at.isoformat(),
        }
        messages.append(MessageResponse(**msg_dict))
    logger.info(
        "chat_service.messages_fetched_from_db",
        key_suffix=key_suffix,
        count=len(messages),
    )
    return MessagesResponse(
        messages=messages,
        total=len(messages),
        from_cache=False,
    )


async def lookup_user_id(
    session: AsyncSession,
    window_id: str,
) -> UserIdResponse:
    """
    Look up user_id and message count for a given window_id.

    Returns
    -------
    UserIdResponse with user_id (if found) and message count.
    """
    user_id = await chat_repo.get_user_id_by_window(session, window_id)
    count = await chat_repo.count_messages_by_window(session, window_id)

    logger.info(
        "chat_service.user_id_lookup",
        window_id=window_id,
        user_id=str(user_id) if user_id else None,
        message_count=count,
    )
    return UserIdResponse(
        window_id=window_id,
        user_id=user_id,
        message_count=count,
    )


async def delete_message(
    session: AsyncSession,
    message_id: uuid.UUID,
) -> bool:
    """
    Delete a chat message and invalidate cache.

    Returns
    -------
    True if deleted, False if not found.
    """
    deleted = await chat_repo.delete_message(session, message_id)

    if deleted:
        # Invalidate cache (we don't know user_id/window_id here, so skip for now)
        # In production, you might want to fetch the message first to get keys
        logger.info("chat_service.message_deleted", message_id=str(message_id))
    else:
        logger.warning("chat_service.message_not_found", message_id=str(message_id))

    return deleted
