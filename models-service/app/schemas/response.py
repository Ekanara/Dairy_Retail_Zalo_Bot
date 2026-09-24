from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.request import Message


class UsageInfo(BaseModel):
    """Token consumption summary."""

    prompt_tokens: int = Field(default=0, description="Input / prompt tokens consumed")
    completion_tokens: int = Field(default=0, description="Output / completion tokens generated")

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class ChatResponse(BaseModel):
    """Full (non-streaming) chat response."""

    message: Message
    usage: UsageInfo = Field(default_factory=UsageInfo)


class StreamChunk(BaseModel):
    """A single Server-Sent Event delta payload."""

    delta: str
