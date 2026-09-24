"""
Async SQLAlchemy engine + session factory for chat-service.

Usage
-----
    from app.db.database import get_session

    async with get_session() as session:
        result = await session.execute(...)

The engine is created once at import time using the DATABASE_URL from
settings. Call `dispose_engine()` during application shutdown to cleanly
release all pooled connections.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

# ── Engine ───────────────────────────────────────────────────────────────────

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,  # set True only for local query debugging
    pool_pre_ping=True,  # drop stale connections before use
    pool_size=10,
    max_overflow=20,
)

# ── Session factory ──────────────────────────────────────────────────────────

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ── Declarative base ─────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ── Dependency / context-manager ─────────────────────────────────────────────

@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context-manager that yields a transactional DB session.

    Commits on clean exit; rolls back and re-raises on any exception.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an AsyncSession.

    Inject with:  session: AsyncSession = Depends(get_db)
    """
    async with get_session() as session:
        yield session


async def dispose_engine() -> None:
    """Release all pooled connections — call during app shutdown."""
    await engine.dispose()
    logger.info("db.engine.disposed", service="chat-service")
