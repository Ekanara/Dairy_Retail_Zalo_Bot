"""
Pydantic schemas for chat-service API.

Request/Response Models
-----------------------
MessageCreate       : Create new chat message (POST body)
MessageResponse     : Single message response
MessagesResponse    : List of messages response
UserIdResponse      : User ID lookup response
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class MessageCreate(BaseModel):
    """Request body for creating a new chat message."""

    user_id: UUID | None = Field(
        None,
        description="Internal user UUID. Can be None if only window_id is known.",
    )
    window_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Zalo user ID (always required)",
    )
    role: str = Field(
        ...,
        pattern="^(user|assistant|system)$",
        description="Message role: 'user', 'assistant', or 'system'",
    )
    content: str = Field(
        ...,
        min_length=1,
        description="Message text content",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional metadata (tool_calls, model_name, etc.)",
    )

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Ensure role is lowercase."""
        return v.lower()


class MessageResponse(BaseModel):
    """Single chat message response."""

    id: UUID
    user_id: UUID | None
    window_id: str
    role: str
    content: str
    metadata: dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True


class MessagesResponse(BaseModel):
    """List of chat messages with metadata."""

    messages: list[MessageResponse]
    total: int = Field(description="Total messages returned")
    from_cache: bool = Field(
        default=False,
        description="Whether data was served from Redis cache",
    )


class UserIdLookupRequest(BaseModel):
    """Request body for looking up user_id from window_id."""

    window_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Zalo user ID",
    )


class UserIdResponse(BaseModel):
    """Response for user_id lookup."""

    window_id: str
    user_id: UUID | None = Field(
        None,
        description="Internal user UUID, or None if never seen",
    )
    message_count: int = Field(
        default=0,
        description="Total messages for this window_id",
    )
