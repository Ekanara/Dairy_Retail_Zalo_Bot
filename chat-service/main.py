"""
chat-service — entry point.

Starts a FastAPI application on port 8007.

Lifespan
--------
- startup  : log service boot, connect Redis, validate DB connectivity
- shutdown : dispose SQLAlchemy pool, close Redis connection

Run
---
    uvicorn main:app --host 0.0.0.0 --port 8007 --reload
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
from app.services.redis_service import redis_cache

logger = get_logger("chat-service.main")


# ── Lifespan ──────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:  # noqa: ARG001
    """Startup / shutdown hooks."""
    t0 = time.monotonic()

    # ── Startup ───────────────────────────────────────────────────────────────
    logger.info(
        "service.startup",
        service="chat-service",
        port=settings.SERVICE_PORT,
        log_level=settings.LOG_LEVEL,
        database_url=settings.DATABASE_URL.split("@")[-1],  # hide credentials
        redis_url=settings.REDIS_URL,
        cache_ttl=settings.CACHE_TTL,
        default_top_k=settings.DEFAULT_TOP_K,
    )

    # Connect to Redis
    try:
        await redis_cache.connect()
        logger.info("service.redis_ready", service="chat-service")
    except Exception as exc:  # noqa: BLE001 — intentional broad catch at startup
        logger.error(
            "service.redis_unavailable",
            service="chat-service",
            error=str(exc),
        )
        # Non-fatal: service can still work without cache

    # Smoke-test DB connectivity so we fail-fast rather than at first request
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        logger.info(
            "service.db_ready",
            service="chat-service",
            latency_ms=round((time.monotonic() - t0) * 1000, 2),
        )
    except Exception as exc:  # noqa: BLE001 — intentional broad catch at startup
        logger.error(
            "service.db_unavailable",
            service="chat-service",
            error=str(exc),
        )
        # Do NOT raise here — let uvicorn start anyway so /health can respond

    yield  # ── application runs ──────────────────────────────────────────────

    # ── Shutdown ──────────────────────────────────────────────────────────────
    await dispose_engine()
    await redis_cache.close()
    logger.info("service.shutdown", service="chat-service")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="chat-service",
    description=(
        "Fast conversation history storage and caching for Magic Sale AI. "
        "Uses Redis (ZSET) for sub-second top-K reads and PostgreSQL for "
        "long-term persistence. Supports dual-key lookup: user_id (UUID) "
        "or window_id (Zalo user ID)."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(router, tags=["chat"])


# ── Global exception handler ──────────────────────────────────────────────────


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    logger.error(
        "unhandled_exception",
        service="chat-service",
        method=request.method,
        url=str(request.url),
        error=str(exc),
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "service": "chat-service"},
    )
