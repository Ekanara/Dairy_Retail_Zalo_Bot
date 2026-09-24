from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Message(BaseModel):
    """A single chat turn."""

    role: Literal["user", "assistant", "system"]
    content: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    """Payload accepted by POST /chat and POST /chat/stream."""

    user_id: str = Field(..., description="Zalo user ID — used to fetch personalised system prompt")
    messages: list[Message] = Field(..., min_length=1, description="Conversation history; last item is the latest user turn")
    stream: bool = Field(default=False, description="Hint: prefer /chat/stream endpoint for streaming responses")
