"""
Pydantic v2 schemas for prompt-service API.

Classes
-------
PromptRead          — Full row returned by GET /prompts/{user_id}/raw
PromptUpdate        — Body for PATCH endpoints (append | replace mode)
SystemPromptResponse — Rendered system-prompt returned by GET /prompts/{user_id}
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PromptRead(BaseModel):
    """Raw per-user prompt fields, as stored in `user_prompts`."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Surrogate PK (UUID)")
    user_id: str = Field(description="Zalo user_id")
    soul_md: str = Field(description="SOUL.md content for this user")
    user_md: str = Field(description="USER.md content for this user")
    memory_md: str = Field(description="MEMORY.md content for this user")
    created_at: datetime = Field(description="Row creation timestamp (UTC)")
    updated_at: datetime = Field(description="Last update timestamp (UTC)")


class PromptUpdate(BaseModel):
    """
    Body for PATCH /prompts/{user_id}/{soul|user|memory}.

    mode="append"      → existing_content + "\\n\\n" + content
    mode="replace"     → overwrite with content exactly
    mode="str_replace" → find old_str (exact, unique match) and replace with new_str
    mode="delete"      → find old_str (exact, unique match) and remove it
    """

    content: str = Field(
        default="",
        description=(
            "New Markdown content to write (used by 'append' and 'replace' modes). "
            "Ignored by 'str_replace' and 'delete' modes."
        ),
    )
    mode: Literal["append", "replace", "str_replace", "delete"] = Field(
        default="append",
        description=(
            "'append' adds to existing content; "
            "'replace' overwrites it; "
            "'str_replace' finds old_str and replaces with new_str; "
            "'delete' finds old_str and removes it"
        ),
    )
    old_str: str | None = Field(
        default=None,
        description=(
            "Required for 'str_replace' and 'delete'. "
            "The exact text to find in the current content. "
            "Must match exactly ONE location (including whitespace/newlines)."
        ),
    )
    new_str: str | None = Field(
        default=None,
        description=(
            "Required for 'str_replace'. "
            "The replacement text. Can be empty string to delete the matched text."
        ),
    )


class SystemPromptResponse(BaseModel):
    """Rendered system prompt ready for injection into an LLM context."""

    user_id: str = Field(description="Zalo user_id this prompt was rendered for")
    system_prompt: str = Field(description="Fully rendered Jinja2 system prompt")
    rendered_at: datetime = Field(description="Timestamp when render completed (UTC)")
