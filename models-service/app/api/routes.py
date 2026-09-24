"""
FastAPI router for models-service.

Endpoints
---------
POST /chat          — Non-streaming: returns full ChatResponse JSON
POST /chat/stream   — Streaming: returns text/event-stream SSE
GET  /health        — Liveness probe
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.core.logger import get_logger
from app.schemas.request import ChatRequest
from app.schemas.response import ChatResponse
from app.services import model_service

logger = get_logger(__name__)

router = APIRouter()


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Non-streaming chat completion",
    response_description="Full assistant message with token usage",
)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Send a conversation to the AI agent and receive a full reply.

    - Fetches personalised system prompt from prompt-service.
    - Runs the Pydantic AI agent (non-streaming).
    - Returns assistant message + token usage.
    """
    logger.info("http_chat_request", extra={"user_id": request.user_id})
    try:
        return await model_service.chat(request)
    except RuntimeError as exc:
        logger.error(
            "chat_upstream_error",
            extra={"user_id": request.user_id, "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Prompt service unavailable",
        ) from exc
    except ValueError as exc:
        logger.error(
            "chat_validation_error",
            extra={"user_id": request.user_id, "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post(
    "/chat/stream",
    summary="Streaming chat completion (SSE)",
    response_description="Server-Sent Events stream of delta chunks",
)
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """
    Send a conversation to the AI agent and receive a streamed reply.

    Response is `text/event-stream` (SSE):
    ```
    data: {"delta": "Chào bạn"}
    data: {"delta": ", bé 6 tháng..."}
    data: [DONE]
    ```

    Consumers: read chunks, strip `data: ` prefix, parse JSON delta;
    stop on `[DONE]`.
    """
    logger.info("http_chat_stream_request", extra={"user_id": request.user_id})
    try:
        return StreamingResponse(
            model_service.chat_stream(request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",  # disable nginx buffering for SSE
            },
        )
    except RuntimeError as exc:
        logger.error(
            "chat_stream_upstream_error",
            extra={"user_id": request.user_id, "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Prompt service unavailable",
        ) from exc


@router.get(
    "/health",
    summary="Liveness probe",
    include_in_schema=True,
)
async def health() -> dict:
    """Simple liveness check — returns 200 when the service is running."""
    return {"status": "ok", "service": "models-service"}
