from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings
from app.core.logger import logger


class Base(DeclarativeBase):
    pass


def _create_engine() -> AsyncEngine:
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
    )
    return engine


engine: AsyncEngine = _create_engine()

AsyncSessionFactory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields an AsyncSession per request."""
    async with AsyncSessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create all tables if they do not exist (used in lifespan for dev convenience)."""
    from app.db import models  # noqa: F401 — import triggers mapper registration

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info(
        "Database tables initialised",
        extra={"event": "db_init", "service": "order-service"},
    )


async def close_db() -> None:
    await engine.dispose()
    logger.info(
        "Database engine disposed",
        extra={"event": "db_close", "service": "order-service"},
    )
