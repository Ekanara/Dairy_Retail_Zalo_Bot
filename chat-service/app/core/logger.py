"""
Structured JSON logger for chat-service.

Every log record emits valid JSON with consistent fields:
  service, event, level, timestamp, plus any extra kwargs.

Usage:
    from app.core.logger import get_logger
    logger = get_logger(__name__)
    logger.info("message.saved", user_id="zalo_123", message_id="uuid")
    logger.error("redis.error", user_id="zalo_123", error=str(exc))
"""

import json
import logging
import sys
import traceback
from datetime import datetime, timezone
from typing import Any


SERVICE_NAME = "chat-service"


class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        # ── base payload ─────────────────────────────────────────────────────
        payload: dict[str, Any] = {
            "service": SERVICE_NAME,
            "level": record.levelname,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            # The first positional arg is treated as the "event" slug
            "event": record.getMessage(),
            "logger": record.name,
        }

        # ── extra fields injected via logger.info("…", extra={…}) ──────────
        # logging passes extra keys directly onto the LogRecord
        skip = {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "message",
            "taskName",
        }
        for key, value in record.__dict__.items():
            if key not in skip:
                payload[key] = value

        # ── exception info ───────────────────────────────────────────────────
        if record.exc_info:
            payload["exception"] = traceback.format_exception(*record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


class _ContextLogger(logging.LoggerAdapter):
    """
    Thin wrapper that lets callers pass structured fields as kwargs:

        logger.info("message.saved", user_id="x", message_id="uuid")

    All kwargs are forwarded into `extra` so they appear in the JSON.
    """

    def process(
        self, msg: str, kwargs: dict[str, Any]
    ) -> tuple[str, dict[str, Any]]:
        extra = dict(self.extra or {})
        # Pull structured fields out of kwargs into extra
        for key in list(kwargs.keys()):
            if key not in ("exc_info", "stack_info", "stacklevel"):
                extra[key] = kwargs.pop(key)
        kwargs["extra"] = extra
        return msg, kwargs


def get_logger(name: str) -> _ContextLogger:
    """
    Return a structured JSON logger bound to *name*.

    Example
    -------
    logger = get_logger(__name__)
    logger.info("message.saved", user_id="123", message_id="uuid")
    """
    raw = logging.getLogger(name)

    if not raw.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_JsonFormatter())
        raw.addHandler(handler)
        raw.propagate = False

    from app.core.config import settings  # late import to avoid circular dep

    raw.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    return _ContextLogger(raw, {})
