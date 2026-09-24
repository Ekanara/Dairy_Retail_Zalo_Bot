"""
FastAPI router for prompt-service.

Endpoints
---------
GET  /health                          — liveness probe
GET  /prompts/{user_id}               — rendered system prompt (SystemPromptResponse)
GET  /prompts/{user_id}/raw           — raw per-user MD fields (PromptRead)
POST /prompts/{user_id}/init          — create/ensure user row
PATCH /prompts/{user_id}/soul         — update SOUL.md
PATCH /prompts/{user_id}/user         — update USER.md
PATCH /prompts/{user_id}/memory       — update MEMORY.md
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.db.database import get_db
from app.repositories import prompt_repo
from app.schemas.prompt import PromptRead, PromptUpdate, SystemPromptResponse
from app.services.prompt_service import prompt_service

logger = get_logger(__name__)

router = APIRouter()


# ── Health ────────────────────────────────────────────────────────────────────


@router.get("/health", summary="Liveness probe")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "prompt-service"}


# ── Rendered system prompt ────────────────────────────────────────────────────


@router.get(
    "/prompts/{user_id}",
    response_model=SystemPromptResponse,
    summary="Get rendered system prompt for user",
)
async def get_system_prompt(
    user_id: str,
    session: AsyncSession = Depends(get_db),
) -> SystemPromptResponse:
    """
    Render the full Jinja2 system prompt for *user_id*.

    - Creates the user row if it does not yet exist (first-chat auto-init).
    - Falls back to template defaults for any empty per-user field.
    """
    t0 = time.monotonic()
    try:
        rendered = await prompt_service.get_rendered_prompt(session, user_id)
    except FileNotFoundError as exc:
        logger.error(
            "routes.get_system_prompt.missing_template",
            user_id=user_id,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prompt architecture file missing: {exc}",
        ) from exc

    latency_ms = round((time.monotonic() - t0) * 1000, 2)
    logger.info(
        "routes.get_system_prompt",
        user_id=user_id,
        prompt_length=len(rendered),
        latency_ms=latency_ms,
    )
    return SystemPromptResponse(
        user_id=user_id,
        system_prompt=rendered,
        rendered_at=datetime.now(tz=timezone.utc),
    )


# ── Raw MD fields ─────────────────────────────────────────────────────────────


@router.get(
    "/prompts/{user_id}/raw",
    response_model=PromptRead,
    summary="Get raw per-user Markdown files",
)
async def get_raw_prompts(
    user_id: str,
    session: AsyncSession = Depends(get_db),
) -> PromptRead:
    """
    Return the raw `soul_md`, `user_md`, `memory_md` stored in the DB.

    Creates the user row with empty defaults if it does not yet exist.
    """
    row = await prompt_repo.get_or_create(session, user_id)
    logger.info("routes.get_raw_prompts", user_id=user_id, row_id=str(row.id))
    return PromptRead.model_validate(row)


# ── View single field ─────────────────────────────────────────────────────


@router.get(
    "/prompts/{user_id}/{field_name}",
    summary="View raw content of a single field (soul|user|memory)",
)
async def get_field_content(
    user_id: str,
    field_name: str,
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """
    Return raw Markdown content of a single field with line numbers.

    Used by AI to inspect content before making str_replace edits.
    """
    field_map = {"soul": "soul_md", "user": "user_md", "memory": "memory_md"}
    db_field = field_map.get(field_name)
    if db_field is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown field '{field_name}'. Expected: soul, user, memory",
        )

    row = await prompt_repo.get_or_create(session, user_id)
    content: str = getattr(row, db_field) or ""

    # Add line numbers for AI reference
    lines = content.split("\n")
    numbered = "\n".join(f"{i:3}| {line}" for i, line in enumerate(lines, 1))

    logger.info(
        "routes.get_field_content",
        user_id=user_id,
        field=db_field,
        content_length=len(content),
    )
    return {
        "user_id": user_id,
        "field": field_name,
        "content": content,
        "content_numbered": numbered,
        "line_count": str(len(lines)),
    }


# ── Init ──────────────────────────────────────────────────────────────────────


@router.post(
    "/prompts/{user_id}/init",
    response_model=PromptRead,
    status_code=status.HTTP_201_CREATED,
    summary="Initialise prompt row for a new user",
)
async def init_user_prompt(
    user_id: str,
    session: AsyncSession = Depends(get_db),
) -> PromptRead:
    """
    Ensure a `user_prompts` row exists for *user_id*.

    Idempotent — returns the existing row if already present.
    Returns 201 always (caller can treat it as "upsert").
    """
    row = await prompt_service.init_user(session, user_id)
    logger.info("routes.init_user_prompt", user_id=user_id, row_id=str(row.id))
    return PromptRead.model_validate(row)


# ── PATCH helpers (DRY) ───────────────────────────────────────────────────────


async def _patch_field(
    user_id: str,
    field: str,
    body: PromptUpdate,
    session: AsyncSession,
) -> PromptRead:
    """Shared logic for all three PATCH endpoints."""
    try:
        row = await prompt_repo.update_field(
            session,
            user_id=user_id,
            field=field,
            content=body.content,
            mode=body.mode,
            old_str=body.old_str,
            new_str=body.new_str,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    logger.info(
        "routes.patch_field",
        user_id=user_id,
        field=field,
        mode=body.mode,
        content_len=len(body.content),
    )
    return PromptRead.model_validate(row)


# ── PATCH /prompts/{user_id}/soul ─────────────────────────────────────────────


@router.patch(
    "/prompts/{user_id}/soul",
    response_model=PromptRead,
    summary="Update SOUL.md for user",
)
async def patch_soul(
    user_id: str,
    body: PromptUpdate,
    session: AsyncSession = Depends(get_db),
) -> PromptRead:
    """
    Update the `soul_md` field.

    `mode="append"` (default) — adds content after existing text.
    `mode="replace"` — overwrites the field entirely.
    """
    return await _patch_field(user_id, "soul_md", body, session)


# ── PATCH /prompts/{user_id}/user ─────────────────────────────────────────────


@router.patch(
    "/prompts/{user_id}/user",
    response_model=PromptRead,
    summary="Update USER.md for user",
)
async def patch_user_profile(
    user_id: str,
    body: PromptUpdate,
    session: AsyncSession = Depends(get_db),
) -> PromptRead:
    """
    Update the `user_md` field (customer name, preferred brands, history…).
    """
    return await _patch_field(user_id, "user_md", body, session)


# ── PATCH /prompts/{user_id}/memory ───────────────────────────────────────────


@router.patch(
    "/prompts/{user_id}/memory",
    response_model=PromptRead,
    summary="Update MEMORY.md for user",
)
async def patch_memory(
    user_id: str,
    body: PromptUpdate,
    session: AsyncSession = Depends(get_db),
) -> PromptRead:
    """
    Update the `memory_md` field (sales patterns, anti-patterns, insights).

    Per architecture rules, this should only be called after a confirmed sale.
    """
    return await _patch_field(user_id, "memory_md", body, session)
