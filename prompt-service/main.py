"""
prompt-service — entry point.

Starts a FastAPI application on port 8001.

Lifespan
--------
- startup  : log service boot, validate DB connectivity
- shutdown : dispose SQLAlchemy connection pool cleanly

Run
---
    uvicorn main:app --host 0.0.0.0 --port 8001 --reload
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.routes import router
from app.core.config import settings
from app.core.logger import get_logger
from app.db.database import AsyncSessionLocal, dispose_engine

logger = get_logger("prompt-service.main")


# ── Lifespan ──────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:  # noqa: ARG001
    """Startup / shutdown hooks."""
    t0 = time.monotonic()

    # ── Startup ───────────────────────────────────────────────────────────────
    logger.info(
        "service.startup",
        service="prompt-service",
        port=8001,
        log_level=settings.LOG_LEVEL,
        prompt_arch_dir=settings.PROMPT_ARCH_DIR,
    )

    # Smoke-test DB connectivity so we fail-fast rather than at first request
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        logger.info(
            "service.db_ready",
            service="prompt-service",
            latency_ms=round((time.monotonic() - t0) * 1000, 2),
        )
    except Exception as exc:  # noqa: BLE001 — intentional broad catch at startup
        logger.error(
            "service.db_unavailable",
            service="prompt-service",
            error=str(exc),
        )
        # Do NOT raise here — let uvicorn start anyway so /health can respond

    yield  # ── application runs ──────────────────────────────────────────────

    # ── Shutdown ──────────────────────────────────────────────────────────────
    await dispose_engine()
    logger.info("service.shutdown", service="prompt-service")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="prompt-service",
    description=(
        "Personalised meta-prompt engine for Magic Sale AI. "
        "Manages per-user SOUL / USER / MEMORY Markdown files and renders "
        "the Jinja2 system-prompt template for each Zalo user_id."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(router, tags=["prompts"])


# ── Global exception handler ──────────────────────────────────────────────────


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    logger.error(
        "unhandled_exception",
        service="prompt-service",
        method=request.method,
        url=str(request.url),
        error=str(exc),
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "service": "prompt-service"},
    )
