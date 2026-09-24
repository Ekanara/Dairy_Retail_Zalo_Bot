"""
RAG Service entrypoint.

A dynamic RAG service supporting multiple methods including:
- Hybrid search (dense + sparse vectors)
- RRF reranking with TEI
- MMR diversity filtering
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.core import logger, settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Args:
        app: FastAPI application instance
    """
    # Startup
    logger.info(
        "Starting RAG service",
        extra={
            "service": settings.service_name,
            "port": settings.service_port,
        }
    )

    # Initialize services (lazy loading on first use)
    # No explicit startup needed for current services

    yield

    # Shutdown
    logger.info("Shutting down RAG service")


# Create FastAPI application
app = FastAPI(
    title="RAG Service",
    description="Dynamic RAG service with hybrid search, reranking, and MMR filtering",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api/v1", tags=["rag"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": settings.service_name,
        "version": "1.0.0",
        "status": "running",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.service_port,
        reload=True,
        log_level=settings.log_level.lower(),
    )
