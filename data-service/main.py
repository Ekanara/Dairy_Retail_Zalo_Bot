from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI

from app.api.routes import router
from app.core.logger import get_logger
from app.db.database import Base, engine

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Create all tables on startup (idempotent — safe to run every boot).
    Alembic handles schema *migrations*; this ensures tables exist in
    development / first-run scenarios without running alembic manually.
    """
    logger.info(
        "data-service starting up — ensuring DB tables exist",
        extra={"action": "startup"},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("DB tables verified", extra={"action": "startup"})

    yield

    logger.info(
        "data-service shutting down — disposing engine",
        extra={"action": "shutdown"},
    )
    await engine.dispose()


app = FastAPI(
    title="data-service",
    description="Product catalog CRUD API for Magic Sale AI",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router)
