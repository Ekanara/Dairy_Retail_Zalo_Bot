"""
Chat service — background orchestrator.

Flow:
  1. Build message list from user text
  2. Call models-service for an AI reply
  3. Push reply back to the user via Zalo API
  4. Log full round-trip latency

This coroutine is always executed as a FastAPI BackgroundTask, which means:
  - It MUST NOT propagate exceptions (the worker silently discards them)
  - It MUST always attempt to send some reply to the user
  - Every error MUST be logged with full context before being swallowed

Exception policy (no bare `except`):
  We catch the specific exception families that can realistically occur here.
  Anything truly unexpected is caught last as BaseException so we can at
  least log it — but we still name the type.
"""

import asyncio
import re
import time
from collections import defaultdict, deque

from app.clients.model_client import model_client
from app.clients.zalo_client import zalo_client
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger("chat-service")

# Shown to the user when the entire pipeline fails
_FALLBACK_REPLY = (
    "Xin lỗi, hệ thống đang bận. Bạn vui lòng nhắn lại sau nhé! 🙏"
)
_MAX_TURNS = 10
# Per-user rolling chat memory: keep 10 turns => 20 messages (user+assistant).
_history: dict[str, deque[dict[str, str]]] = defaultdict(
    lambda: deque(maxlen=_MAX_TURNS * 2)
)
_history_lock = asyncio.Lock()


async def handle_message(user_id: str, message_text: str) -> None:
    """
    Background task: receive *message_text* from *user_id*,
    fetch an AI reply, and send it back via Zalo.
    """
    start = time.monotonic()

    try:
        async with _history_lock:
            messages = list(_history[user_id])
            messages.append({"role": "user", "content": message_text})

        ai_response = await model_client.chat(user_id=user_id, messages=messages)
        async with _history_lock:
            user_history = _history[user_id]
            user_history.append({"role": "user", "content": message_text})
            user_history.append({"role": "assistant", "content": ai_response})
        # Strip QR URL from text before sending (send as image separately)
        qr_match = re.search(r'(https://img\.vietqr\.io/image/[^\s]+)', ai_response)
        clean_response = re.sub(r'\n?Mã QR thanh toán: https://img\.vietqr\.io/image/[^\s]+', '', ai_response) if qr_match else ai_response
        sent = await zalo_client.send_message(user_id=user_id, text=clean_response.strip())

        # Send QR payment image if present
        if qr_match:
            await zalo_client.send_photo(
                user_id=user_id,
                image_url=qr_match.group(1),
                caption="Ma QR thanh toan",
            )

        latency_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "chat_handled",
            extra={
                "user_id": user_id,
                "message_len": len(message_text),
                "response_len": len(ai_response),
                "sent_ok": sent,
                "latency_ms": latency_ms,
                "history_messages_sent": len(messages),
                **(
                    {
                        "message_text": message_text,
                        "ai_response": ai_response,
                    }
                    if settings.TRACE_CHAT_CONTENT
                    else {}
                ),
            },
        )

    except (OSError, ValueError, RuntimeError, asyncio.CancelledError) as exc:
        # Known recoverable / network-level errors
        await _log_and_fallback(user_id, exc, start)

    except Exception as exc:  # noqa: BLE001 — last-resort safety net, logged fully
        # Unexpected error: log with traceback, still attempt fallback reply
        await _log_and_fallback(user_id, exc, start)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _log_and_fallback(user_id: str, exc: Exception, start: float) -> None:
    """Log *exc* with full context, then attempt a fallback reply to the user."""
    latency_ms = int((time.monotonic() - start) * 1000)
    logger.error(
        "chat_handle_error",
        extra={
            "user_id": user_id,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "latency_ms": latency_ms,
        },
        exc_info=exc,
    )

    try:
        await zalo_client.send_message(user_id=user_id, text=_FALLBACK_REPLY)
    except (OSError, ValueError, RuntimeError) as fallback_exc:
        # Fallback itself failed — log and give up; do NOT raise
        logger.error(
            "chat_fallback_send_failed",
            extra={
                "user_id": user_id,
                "error_type": type(fallback_exc).__name__,
                "error": str(fallback_exc),
            },
        )
