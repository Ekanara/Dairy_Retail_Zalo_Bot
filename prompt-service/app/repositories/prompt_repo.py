"""
Data-access layer for the `user_prompts` table.

All functions accept an `AsyncSession` (injected by the caller) so they
compose cleanly inside larger transactions when needed.

Public API
----------
get_by_user_id(session, user_id)               → UserPrompt | None
create_default(session, user_id)               → UserPrompt
get_or_create(session, user_id)                → UserPrompt
update_field(session, user_id, field, content, mode) → UserPrompt
"""

from __future__ import annotations

import time
from typing import Literal

import asyncpg  # type: ignore[import]
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.db.models import UserPrompt

logger = get_logger(__name__)

# Fields that callers are allowed to update
_ALLOWED_FIELDS: frozenset[str] = frozenset({"soul_md", "user_md", "memory_md"})


async def get_by_user_id(
    session: AsyncSession,
    user_id: str,
) -> UserPrompt | None:
    """
    Return the UserPrompt row for *user_id*, or None if not found.

    Raises
    ------
    asyncpg.exceptions.PostgresConnectionError  — if DB is unreachable
    """
    t0 = time.monotonic()
    stmt = select(UserPrompt).where(UserPrompt.user_id == user_id)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    latency_ms = round((time.monotonic() - t0) * 1000, 2)

    logger.info(
        "prompt_repo.get_by_user_id",
        user_id=user_id,
        found=row is not None,
        latency_ms=latency_ms,
    )
    return row


async def create_default(
    session: AsyncSession,
    user_id: str,
) -> UserPrompt:
    """
    Insert a new UserPrompt row with empty-string defaults.

    The caller is responsible for committing (or the surrounding transaction).
    """
    t0 = time.monotonic()
    row = UserPrompt(
        user_id=user_id,
        soul_md="",
        user_md="",
        memory_md="",
    )
    session.add(row)
    await session.flush()  # assign PK + timestamps without committing
    await session.refresh(row)
    latency_ms = round((time.monotonic() - t0) * 1000, 2)

    logger.info(
        "prompt_repo.create_default",
        user_id=user_id,
        row_id=str(row.id),
        latency_ms=latency_ms,
    )
    logger.warning(
        "prompt_repo.profile_initialized_empty",
        user_id=user_id,
        row_id=str(row.id),
        note="new_user_created_with_empty_soul_user_memory",
    )
    return row


async def get_or_create(
    session: AsyncSession,
    user_id: str,
) -> UserPrompt:
    """
    Return the existing row for *user_id*, or create one with defaults.

    Handles the rare race-condition where two requests try to create the
    same user simultaneously by catching IntegrityError and re-fetching.
    """
    row = await get_by_user_id(session, user_id)
    if row is not None:
        return row

    try:
        row = await create_default(session, user_id)
    except IntegrityError:
        # Another concurrent request already inserted — rollback the failed
        # flush and re-fetch the committed row.
        await session.rollback()
        logger.info(
            "prompt_repo.get_or_create.race_condition_handled",
            user_id=user_id,
        )
        row = await get_by_user_id(session, user_id)
        if row is None:
            # Should not happen — surface as a clear error
            raise RuntimeError(
                f"UserPrompt for user_id={user_id!r} vanished after race-condition retry"
            )

    return row


async def update_field(
    session: AsyncSession,
    user_id: str,
    field: str,
    content: str = "",
    mode: Literal["append", "replace", "str_replace", "delete"] = "append",
    old_str: str | None = None,
    new_str: str | None = None,
) -> UserPrompt:
    """
    Update one text field (soul_md | user_md | memory_md) for *user_id*.

    Parameters
    ----------
    field   : one of 'soul_md', 'user_md', 'memory_md'
    content : new Markdown content (used by 'append' and 'replace')
    mode    : 'append'      → current + "\\n\\n" + content
              'replace'     → overwrite with content
              'str_replace' → find old_str, replace with new_str (exact, unique)
              'delete'      → find old_str and remove it
    old_str : exact text to find (required for 'str_replace' and 'delete')
    new_str : replacement text (required for 'str_replace')

    Returns
    -------
    The refreshed UserPrompt row after the write.

    Raises
    ------
    ValueError           — if field invalid, old_str not found, or multiple matches
    asyncpg.exceptions.* — propagated DB errors (caller must catch)
    """
    if field not in _ALLOWED_FIELDS:
        raise ValueError(
            f"Field {field!r} is not updatable. Allowed: {sorted(_ALLOWED_FIELDS)}"
        )

    row = await get_or_create(session, user_id)
    current: str = getattr(row, field) or ""

    if mode == "append":
        new_value = (current + "\n\n" + content) if current.strip() else content

    elif mode == "replace":
        new_value = content

    elif mode == "str_replace":
        if old_str is None:
            raise ValueError("old_str is required for mode='str_replace'.")
        if new_str is None:
            raise ValueError("new_str is required for mode='str_replace'.")

        match_count = current.count(old_str)
        if match_count == 0:
            # Build a helpful snippet around potential near-matches
            preview = current[:500] if current else "(empty file)"
            raise ValueError(
                f"No match found for old_str in {field}.\n\n"
                f"old_str ({len(old_str)} chars):\n"
                f"  {old_str!r}\n\n"
                f"Current content preview:\n"
                f"  {preview}\n\n"
                f"Tip: Use command='view' first to see exact content, "
                f"then copy the exact text including whitespace/newlines."
            )
        if match_count > 1:
            raise ValueError(
                f"Found {match_count} matches for old_str in {field}. "
                f"Please provide more surrounding context to make it unique.\n\n"
                f"old_str:\n  {old_str!r}"
            )

        new_value = current.replace(old_str, new_str, 1)

    elif mode == "delete":
        if old_str is None:
            raise ValueError("old_str is required for mode='delete'.")

        match_count = current.count(old_str)
        if match_count == 0:
            preview = current[:500] if current else "(empty file)"
            raise ValueError(
                f"No match found for old_str in {field}.\n\n"
                f"old_str ({len(old_str)} chars):\n"
                f"  {old_str!r}\n\n"
                f"Current content preview:\n"
                f"  {preview}\n\n"
                f"Tip: Use command='view' first to see exact content."
            )
        if match_count > 1:
            raise ValueError(
                f"Found {match_count} matches for old_str in {field}. "
                f"Please provide more surrounding context to make it unique.\n\n"
                f"old_str:\n  {old_str!r}"
            )

        new_value = current.replace(old_str, "", 1).strip()

    else:
        raise ValueError(
            f"Unknown mode {mode!r}. "
            f"Expected 'append', 'replace', 'str_replace', or 'delete'."
        )

    char_delta = len(new_value) - len(current)
    setattr(row, field, new_value)
    await session.flush()
    await session.refresh(row)

    logger.info(
        "prompt_repo.update_field",
        user_id=user_id,
        field=field,
        mode=mode,
        char_delta=char_delta,
        new_length=len(new_value),
    )
    return row
