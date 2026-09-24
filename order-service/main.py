from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings
from app.core.logger import logger
from app.db.database import close_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info(
        "order-service starting",
        extra={"event": "startup", "service": "order-service"},
    )
    await init_db()
    yield
    await close_db()
    logger.info(
        "order-service stopped",
        extra={"event": "shutdown", "service": "order-service"},
    )


app = FastAPI(
    title="Order Service — Magic Sale AI",
    description=(
        "Quản lý vòng đời đơn hàng sữa: tạo order, theo dõi tồn kho, "
        "cập nhật trạng thái với ACID transaction đầy đủ."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8003,
        reload=False,
        log_config=None,   # disable uvicorn default logger; use our structured logger
    )
