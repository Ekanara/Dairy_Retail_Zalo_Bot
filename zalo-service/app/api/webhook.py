"""
Webhook router — receives inbound events from Zalo Platform.

Critical contract with Zalo:
  - Must return HTTP 200 within ~5 s or Zalo retries / marks OA offline
  - AI processing happens in a BackgroundTask AFTER the 200 is returned

Signature verification:
  - When WEBHOOK_SECRET_TOKEN is set, verify the X-ZEvent-Signature header
  - HMAC-SHA256(key=WEBHOOK_SECRET_TOKEN, msg=raw_body)
  - If verification fails → 403 (do NOT process the event)
"""

import hashlib
import hmac

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import ValidationError

from pydantic import BaseModel

from app.clients.zalo_client import zalo_client
from app.core.config import settings
from app.core.logger import get_logger
from app.schemas.zalo_event import ZaloEvent
from app.services.chat_service import handle_message

logger = get_logger("webhook")
router = APIRouter()


# ---------------------------------------------------------------------------
# Internal API — called by other services (not Zalo Platform)
# ---------------------------------------------------------------------------

class SendPhotoRequest(BaseModel):
    user_id: str
    image_url: str
    caption: str = ""


class SendMessageRequest(BaseModel):
    user_id: str
    text: str


@router.post("/internal/send-photo")
async def send_photo(payload: SendPhotoRequest):
    """Internal endpoint for other services to send images via Zalo."""
    sent = await zalo_client.send_photo(
        user_id=payload.user_id,
        image_url=payload.image_url,
        caption=payload.caption,
    )
    return {"sent": sent}


@router.post("/internal/send-message")
async def internal_send_message(payload: SendMessageRequest):
    """Internal endpoint for other services to send text messages via Zalo."""
    sent = await zalo_client.send_message(
        user_id=payload.user_id,
        text=payload.text,
    )
    return {"sent": sent}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _verify_signature(secret: str, raw_body: bytes, header_sig: str) -> bool:
    """
    Return True if *header_sig* matches HMAC-SHA256 of *raw_body*
    signed with *secret*.

    Uses hmac.compare_digest to prevent timing-based attacks.
    """
    expected = hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, header_sig)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receive an event from Zalo Platform.

    Steps:
      1. Read raw body (needed for HMAC verification)
      2. Verify signature when WEBHOOK_SECRET_TOKEN is configured
      3. Parse ZaloEvent schema
      4. If text message → enqueue background AI task
      5. Return {"status": "ok"} immediately (HTTP 200)
    """
    raw_body = await request.body()

    # ------------------------------------------------------------------
    # Step 1 — Signature verification (skip when no secret is configured)
    # ------------------------------------------------------------------
    if settings.WEBHOOK_SECRET_TOKEN:
        header_sig = request.headers.get("X-ZEvent-Signature", "")
        if not header_sig:
            logger.warning(
                "webhook_signature_missing",
                extra={"client_ip": request.client.host if request.client else "unknown"},
            )
            raise HTTPException(status_code=403, detail="Missing signature")

        if not _verify_signature(settings.WEBHOOK_SECRET_TOKEN, raw_body, header_sig):
            logger.warning(
                "webhook_signature_invalid",
                extra={"client_ip": request.client.host if request.client else "unknown"},
            )
            raise HTTPException(status_code=403, detail="Invalid signature")

    # ------------------------------------------------------------------
    # Step 2 — Parse event
    # ------------------------------------------------------------------
    try:
        event_data = await request.json()
        event = ZaloEvent(**event_data)
    except ValidationError as exc:
        logger.warning(
            "webhook_schema_invalid",
            extra={"validation_errors": exc.errors()},
        )
        # Return 200 so Zalo does not keep retrying a malformed payload
        return {"status": "ignored", "reason": "schema_invalid"}
    except ValueError as exc:
        # request.json() raises ValueError on malformed JSON
        logger.warning(
            "webhook_json_invalid",
            extra={"error": str(exc)},
        )
        return {"status": "ignored", "reason": "json_invalid"}

    logger.info(
        "webhook_received",
        extra={
            "event_type": event.event_name,
            "user_id": event.user_id,
            "has_message": event.message is not None,
        },
    )

    # ------------------------------------------------------------------
    # Step 3 — Dispatch AI processing for text messages only
    # ------------------------------------------------------------------
    if event.is_text_message:
        background_tasks.add_task(
            handle_message,
            event.user_id,
            event.message_text,
        )
    else:
        logger.info(
            "webhook_event_skipped",
            extra={
                "event_type": event.event_name,
                "user_id": event.user_id,
                "reason": "not_text_message",
            },
        )

    # Respond 200 IMMEDIATELY — do NOT await AI processing here
    return {"status": "ok"}


@router.get("/health")
async def health():
    """Lightweight liveness probe."""
    return {"status": "ok", "service": "zalo-service"}
