"""
FastAPI router for chat-service.

Endpoints
---------
POST   /chat/messages              — Save new chat message
GET    /chat/messages              — Get top-K messages (by user_id or window_id)
GET    /chat/user-id               — Lookup user_id from window_id
DELETE /chat/messages/{message_id} — Delete a message
GET    /health                     — Liveness probe
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.db.database import get_db
from app.schemas.chat import (
    MessageCreate,
    MessageResponse,
    MessagesResponse,
    UserIdResponse,
)
from app.services import chat_service

logger = get_logger(__name__)

router = APIRouter()


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/health", summary="Liveness probe")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "chat-service"}


# ── Save message ──────────────────────────────────────────────────────────────

@router.post(
    "/chat/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save a new chat message",
)
async def save_message(
    msg_data: MessageCreate,
    session: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    Save a new chat message to PostgreSQL and update Redis cache.

    **Request body:**
    - `user_id` (optional): Internal user UUID
    - `window_id` (required): Zalo user ID
    - `role` (required): 'user', 'assistant', or 'system'
    - `content` (required): Message text
    - `metadata` (optional): Additional metadata dict

    **Returns:** Created message with ID and timestamp.
    """
    try:
        return await chat_service.save_message(session, msg_data)
    except Exception as exc:
        logger.error(
            "routes.save_message.error",
            window_id=msg_data.window_id,
            error=str(exc),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save message: {exc}",
        ) from exc


# ── Get messages ──────────────────────────────────────────────────────────────

@router.get(
    "/chat/messages",
    response_model=MessagesResponse,
    summary="Get top-K chat messages",
)
async def get_messages(
    user_id: uuid.UUID | None = Query(None, description="Internal user UUID"),
    window_id: str | None = Query(None, description="Zalo user ID"),
    limit: int = Query(100, ge=1, le=1000, description="Max messages to return"),
    session: AsyncSession = Depends(get_db),
) -> MessagesResponse:
    """
    Fetch top-K messages with Redis-first caching strategy.

    **Query parameters:**
    - `user_id` (optional): Filter by internal user UUID
    - `window_id` (optional): Filter by Zalo user ID
    - `limit` (optional): Max messages (default 100, max 1000)

    **At least one of `user_id` or `window_id` must be provided.**

    **Returns:** List of messages (newest first), cache status, and total count.
    """
    try:
        return await chat_service.get_messages(
            session,
            user_id=user_id,
            window_id=window_id,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error(
            "routes.get_messages.error",
            user_id=str(user_id) if user_id else None,
            window_id=window_id,
            error=str(exc),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch messages: {exc}",
        ) from exc


# ── Lookup user_id ────────────────────────────────────────────────────────────

@router.get(
    "/chat/user-id",
    response_model=UserIdResponse,
    summary="Lookup user_id from window_id",
)
async def lookup_user_id(
    window_id: str = Query(..., description="Zalo user ID"),
    session: AsyncSession = Depends(get_db),
) -> UserIdResponse:
    """
    Look up the internal user_id associated with a window_id.

    **Query parameters:**
    - `window_id` (required): Zalo user ID

    **Returns:** user_id (if found), window_id, and total message count.
    """
    try:
        return await chat_service.lookup_user_id(session, window_id)
    except Exception as exc:
        logger.error(
            "routes.lookup_user_id.error",
            window_id=window_id,
            error=str(exc),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to lookup user_id: {exc}",
        ) from exc


# ── Delete message ────────────────────────────────────────────────────────────

@router.delete(
    "/chat/messages/{message_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete a chat message",
)
async def delete_message(
    message_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    """
    Delete a chat message by ID.

    **Path parameters:**
    - `message_id`: UUID of the message to delete

    **Returns:** 204 No Content on success, 404 if not found.
    """
    deleted = await chat_service.delete_message(session, message_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Message {message_id} not found",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
