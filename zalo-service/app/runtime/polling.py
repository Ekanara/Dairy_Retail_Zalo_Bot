"""
Polling runtime using `zalo_bot` SDK (same strategy as trash/app_fake).

Usage:
    python main.py --mode polling
"""

import asyncio
import json
from typing import Any

from app.clients.zalo_client import zalo_client
from app.core.config import settings
from app.core.logger import get_logger
from app.services.chat_service import handle_message

logger = get_logger("polling")
_ERROR_BACKOFF = 2.0
_PRIMARY_ID_SOURCES = {"message.from.id", "message.sender.id", "message.from_id"}


async def run_polling() -> None:
    """Poll updates and dispatch text messages to chat handler."""
    logger.info("polling_started")
    while True:
        try:
            updates = await zalo_client.get_updates(timeout=10)
            logger.info("polling_tick", extra={"updates_fetched": len(updates)})
            for update in updates:
                # --- DEBUG: log raw payload để chẩn đoán user_id sai ---
                try:
                    raw = update.to_dict() if hasattr(update, "to_dict") else update
                    raw_str = json.dumps(raw, ensure_ascii=False, default=str)
                    logger.debug(
                        "polling_raw_update",
                        extra={"raw_payload": raw_str[:1000]},
                    )
                except Exception:  # noqa: BLE001
                    pass
                # ----------------------------------------------------------

                parsed = _parse_incoming_message(update)
                if not parsed:
                    logger.debug(
                        "polling_update_skipped",
                        extra={"reason": "parse_failed_or_not_text"},
                    )
                    continue

                user_id, text, id_source = parsed
                if id_source not in _PRIMARY_ID_SOURCES:
                    logger.warning(
                        "polling_user_id_fallback_used",
                        extra={
                            "user_id": user_id,
                            "id_source": id_source,
                            "reason": "preferred_source_missing",
                        },
                    )
                logger.info(
                    "polling_new_message",
                    extra={
                        "user_id": user_id,
                        "text_len": len(text),
                        "id_source": id_source,  # <-- field nào đang được dùng
                        **(
                            {"message_text": text}
                            if settings.TRACE_CHAT_CONTENT
                            else {}
                        ),
                    },
                )
                asyncio.ensure_future(handle_message(user_id=user_id, message_text=text))

        except Exception as exc:  # noqa: BLE001
            logger.error(
                "polling_runtime_error",
                extra={"error_type": type(exc).__name__, "error": str(exc)},
            )
            await asyncio.sleep(_ERROR_BACKOFF)


def _parse_incoming_message(update: Any) -> tuple[str, str, str] | None:
    """
    Parse update shape from zalo_bot:
      - {"update": {...}} or {"result": {...}} or direct {...}
      - Accept only sender identity fields (message.from.id / message.sender.id)
      - Reject chat-level ids to avoid cross-user history contamination
    """
    candidate = _unwrap_update(update)
    if not isinstance(candidate, dict):
        return None

    message = _unwrap_object(candidate.get("message"))
    if not isinstance(message, dict):
        return None

    user_id, id_source = _extract_user_id(message=message, root=candidate)
    text = message.get("text")
    if user_id is None or not isinstance(text, str):
        return None

    normalized = text.strip()
    if not normalized:
        return None

    return str(user_id), normalized, id_source


def _extract_user_id(message: dict[str, Any], root: dict[str, Any]) -> tuple[str | None, str]:
    """
    Extract a stable user_id from multiple possible SDK payload shapes.

    Priority:
      1) message.from.id / message.from_id
      2) message.sender.id
      3) root.sender.id

    Note:
      We intentionally do NOT use message.chat.id because it can be chat-level
      (not user-level) in some payload variants and may collapse multiple users
      into one shared conversation history key.
    """
    from_obj = _unwrap_object(message.get("from"))
    if from_obj.get("id") is not None:
        return str(from_obj["id"]), "message.from.id"
    if message.get("from_id") is not None:
        return str(message["from_id"]), "message.from_id"

    sender = _unwrap_object(message.get("sender"))
    if sender.get("id") is not None:
        return str(sender["id"]), "message.sender.id"

    root_sender = _unwrap_object(root.get("sender"))
    if root_sender.get("id") is not None:
        return str(root_sender["id"]), "root.sender.id"

    return None, "none"


def _unwrap_update(update: Any) -> dict[str, Any]:
    if hasattr(update, "to_dict") and callable(update.to_dict):
        update = update.to_dict()

    if not isinstance(update, dict):
        return {}

    if isinstance(update.get("update"), dict):
        return update["update"]
    if isinstance(update.get("result"), dict):
        return update["result"]
    return update


def _unwrap_object(obj: Any) -> dict[str, Any]:
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        obj = obj.to_dict()
    return obj if isinstance(obj, dict) else {}
