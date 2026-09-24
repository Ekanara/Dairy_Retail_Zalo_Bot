"""
Prompt rendering service for prompt-service.

Strategy — how system_prompt.md is rendered
--------------------------------------------
The master template (`system_prompt.md`) uses Jinja2 `{% include %}` tags
for every component file, e.g.:

    {% include "SOUL.md" %}
    {% include "USER.md" %}
    {% include "MEMORY.md" %}
    {% include "AGENTS.md" %}
    {% include "IDENTITY.md" %}
    {% include "TOOLS.md" %}

SOUL / USER / MEMORY are *per-user* — their content lives in the
`user_prompts` table, not on disk.

To inject per-user content without touching the template we use a custom
Jinja2 `BaseLoader` that:

1. For SOUL.md / USER.md / MEMORY.md  → returns the per-user string loaded
   from the DB.
2. For all other files (AGENTS.md, IDENTITY.md, TOOLS.md, system_prompt.md)
   → reads directly from the `prompt_architechture/` directory.

This keeps the template unchanged and makes rendering fully deterministic.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from jinja2 import BaseLoader, Environment, TemplateNotFound
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logger import get_logger
from app.db.models import UserPrompt
from app.repositories import prompt_repo

logger = get_logger(__name__)


# ── Custom Jinja2 loader ──────────────────────────────────────────────────────


class _PerUserLoader(BaseLoader):
    """
    Jinja2 loader that merges on-disk static files with per-user DB content.

    *per_user_overrides* maps filename → string content.
    Any filename NOT in that dict is loaded from *arch_dir*.
    """

    def __init__(
        self,
        arch_dir: Path,
        per_user_overrides: dict[str, str],
    ) -> None:
        self._arch_dir = arch_dir
        self._overrides = per_user_overrides

    def get_source(
        self, environment: Environment, template: str
    ) -> tuple[str, str, None]:
        if template in self._overrides:
            source = self._overrides[template]
            # Return (source, filename, uptodate)
            # uptodate=None means Jinja2 always reloads (fine for our use-case)
            return source, f"<db:{template}>", None  # type: ignore[return-value]

        path = self._arch_dir / template
        if not path.is_file():
            raise TemplateNotFound(template)

        source = path.read_text(encoding="utf-8")
        return source, str(path), None  # type: ignore[return-value]


# ── Service class ─────────────────────────────────────────────────────────────


class PromptService:
    """
    Renders the personalised system prompt for a given user_id.

    The instance is created once at application startup (singleton pattern via
    the module-level `prompt_service` object at the bottom of this file).
    """

    def __init__(self) -> None:
        self._arch_dir = Path(settings.PROMPT_ARCH_DIR)

    # ── internal helpers ──────────────────────────────────────────────────────

    def _read_static(self, filename: str) -> str:
        """Read a static file from prompt_architechture/, raise if missing."""
        path = self._arch_dir / filename
        if not path.is_file():
            raise FileNotFoundError(
                f"Required prompt architecture file not found: {path}"
            )
        return path.read_text(encoding="utf-8")

    def _build_env(self, overrides: dict[str, str]) -> Environment:
        """
        Build a fresh Jinja2 Environment with *overrides* injected.

        A fresh env per render guarantees thread-safety and correct
        per-user content (no cross-user cache pollution).
        """
        return Environment(
            loader=_PerUserLoader(self._arch_dir, overrides),
            autoescape=False,
            keep_trailing_newline=True,
        )

    # ── public API ────────────────────────────────────────────────────────────

    async def get_rendered_prompt(
        self,
        session: AsyncSession,
        user_id: str,
    ) -> str:
        """
        Render `system_prompt.md` with per-user content for *user_id*.

        Steps
        -----
        1. get_or_create the user row from DB
        2. Build Jinja2 env with per-user SOUL/USER/MEMORY from DB
        3. Render system_prompt.md and return the string

        Raises
        ------
        FileNotFoundError — if any required architecture file is missing
        jinja2.TemplateNotFound — if system_prompt.md is missing
        asyncpg.exceptions.* — DB errors (propagated to caller)
        """
        t0 = time.monotonic()

        user_prompt: UserPrompt = await prompt_repo.get_or_create(session, user_id)

        soul_content = user_prompt.soul_md.strip()
        user_content = user_prompt.user_md.strip()
        memory_content = user_prompt.memory_md.strip()

        if not user_content:
            logger.warning(
                "prompt_service.user_profile_empty",
                user_id=user_id,
                row_id=str(user_prompt.id),
                note="rendering_prompt_without_user_md",
            )

        # Inject per-user content as virtual Jinja2 "files"
        # When the template does {% include "SOUL.md" %} it will receive the
        # per-user string instead of the on-disk file.
        overrides: dict[str, str] = {
            "SOUL.md": soul_content,
            "USER.md": user_content,
            "MEMORY.md": memory_content,
        }

        env = self._build_env(overrides)
        template = env.get_template("system_prompt.md")
        rendered: str = template.render(user_id=user_id)

        latency_ms = round((time.monotonic() - t0) * 1000, 2)
        logger.info(
            "prompt_service.rendered",
            user_id=user_id,
            prompt_length=len(rendered),
            soul_source="db" if soul_content else "empty",
            user_source="db" if user_content else "empty",
            memory_source="db" if memory_content else "empty",
            latency_ms=latency_ms,
        )
        return rendered

    async def init_user(
        self,
        session: AsyncSession,
        user_id: str,
    ) -> UserPrompt:
        """
        Ensure a user row exists (create with empty defaults if not).

        Idempotent — safe to call multiple times for the same user_id.
        """
        t0 = time.monotonic()
        row = await prompt_repo.get_or_create(session, user_id)
        latency_ms = round((time.monotonic() - t0) * 1000, 2)
        logger.info(
            "prompt_service.user_init",
            user_id=user_id,
            row_id=str(row.id),
            latency_ms=latency_ms,
        )
        return row

    async def update_soul(
        self,
        session: AsyncSession,
        user_id: str,
        content: str,
        mode: str = "append",
    ) -> UserPrompt:
        return await prompt_repo.update_field(
            session, user_id, "soul_md", content, mode  # type: ignore[arg-type]
        )

    async def update_user(
        self,
        session: AsyncSession,
        user_id: str,
        content: str,
        mode: str = "append",
    ) -> UserPrompt:
        return await prompt_repo.update_field(
            session, user_id, "user_md", content, mode  # type: ignore[arg-type]
        )

    async def update_memory(
        self,
        session: AsyncSession,
        user_id: str,
        content: str,
        mode: str = "append",
    ) -> UserPrompt:
        return await prompt_repo.update_field(
            session, user_id, "memory_md", content, mode  # type: ignore[arg-type]
        )


# ── Module-level singleton ────────────────────────────────────────────────────

prompt_service = PromptService()
