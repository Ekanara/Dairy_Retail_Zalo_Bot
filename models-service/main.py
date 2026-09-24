"""
models-service — FastAPI application entrypoint.

Startup sequence
----------------
1. Load .env → pydantic-settings validates all required vars (MODEL_NAME, API_KEY, BASE_URL).
2. agentskill packages are added to sys.path (skill_tool, memory).
3. ModelClient is initialised (OpenAIChatModel + OpenAIProvider) once at import time.
4. FastAPI app is created, lifespan logging added, router mounted.
5. Uvicorn listens on port 8000.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make agentskill packages importable (skill_tool, memory).
# Search order: AGENTSKILL_DIR env var → sibling directory → git repo root.
def _find_agentskill() -> Path | None:
    import os
    env_dir = os.environ.get("AGENTSKILL_DIR", "").strip()
    if env_dir:
        p = Path(env_dir)
        if p.is_dir():
            return p

    # Sibling directory (standard layout: repo/models-service, repo/agentskill)
    sibling = Path(__file__).resolve().parent.parent / "agentskill"
    if sibling.is_dir():
        return sibling

    # Walk up to find repo root containing agentskill/
    current = Path(__file__).resolve().parent
    for _ in range(6):
        candidate = current / "agentskill"
        if candidate.is_dir() and (candidate / "skill_tool").is_dir():
            return candidate
        current = current.parent

    return None

_agentskill = _find_agentskill()
if _agentskill is not None:
    sys.path.insert(0, str(_agentskill))

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from app.api.routes import router
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Log startup / shutdown events."""
    from app.clients.chat_client import chat_client  # lazy import

    logger.info(
        "models_service_startup",
        extra={
            "model": settings.MODEL_NAME,
            "base_url": settings.BASE_URL,
            "prompt_service_url": settings.PROMPT_SERVICE_URL,
            "mcp_service_url": settings.MCP_SERVICE_URL,
            "chat_service_url": settings.CHAT_SERVICE_URL,
            "mcp_enabled": settings.MCP_ENABLED,
            "chat_history_enabled": settings.CHAT_HISTORY_ENABLED,
        },
    )
    yield
    # Cleanup HTTP client connections
    await chat_client.close()
    logger.info("models_service_shutdown")


app = FastAPI(
    title="Magic Sale AI — Models Service",
    description=(
        "Pydantic AI agent gateway. Accepts chat requests from zalo-service, "
        "fetches personalised system prompts from prompt-service, and streams "
        "or returns AI responses using any OpenAI-compatible LLM backend."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router)
