from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

# Tạo engine một lần duy nhất — share toàn service
_engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    echo=False,
)

_AsyncSessionFactory = async_sessionmaker(
    bind=_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager trả AsyncSession, tự rollback khi có lỗi."""
    async with _AsyncSessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def dispose_engine() -> None:
    """Đóng engine khi shutdown (gọi trong lifespan hook nếu cần)."""
    await _engine.dispose()
    logger.info("db_engine_disposed", extra={"event": "shutdown"})
