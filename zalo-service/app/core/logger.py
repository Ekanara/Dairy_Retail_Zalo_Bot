"""
Structured JSON logger for zalo-service.

Log format (always JSON):
{
  "timestamp": "2026-03-13T22:35:00+07:00",
  "level":     "INFO",
  "service":   "zalo-service",
  "event":     "<event_name>",
  ...extra fields...
}

IMPORTANT: ZALO_BOT_TOKEN MUST NEVER appear in logs.
           Always call mask_token() before logging token values.
"""

import logging
import json
import sys
from datetime import datetime, timezone, timedelta
from typing import Any

# Vietnam timezone  (UTC+7)
_VN_TZ = timezone(timedelta(hours=7))


def mask_token(token: str) -> str:
    """Mask sensitive token — only expose first 4 and last 4 chars."""
    if not token:
        return "****"
    if len(token) <= 8:
        return "****"
    return token[:4] + "****" + token[-4:]


class _JSONFormatter(logging.Formatter):
    """Format every LogRecord as a single-line JSON object."""

    SERVICE_NAME = "zalo-service"

    def format(self, record: logging.LogRecord) -> str:
        now = datetime.now(_VN_TZ).isoformat(timespec="seconds")

        payload: dict[str, Any] = {
            "timestamp": now,
            "level": record.levelname,
            "service": self.SERVICE_NAME,
            "event": record.getMessage(),
        }

        # Merge any extra fields attached via logger.info("event", extra={...})
        _reserved = {
            "args", "asctime", "created", "exc_info", "exc_text", "filename",
            "funcName", "levelname", "levelno", "lineno", "message", "module",
            "msecs", "msg", "name", "pathname", "process", "processName",
            "relativeCreated", "stack_info", "thread", "threadName",
            "taskName",
        }
        for key, value in record.__dict__.items():
            if key not in _reserved:
                payload[key] = value

        # Attach exception traceback if present
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def _build_logger(name: str) -> logging.Logger:
    """Create (or retrieve) a named logger with the JSON handler attached."""
    logger = logging.getLogger(name)

    if logger.handlers:
        # Already configured — return as-is to avoid duplicate handlers
        return logger

    from app.core.config import settings  # late import avoids circular dep

    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JSONFormatter())
    logger.addHandler(handler)
    logger.propagate = False

    return logger


def get_logger(name: str) -> logging.Logger:
    """Public factory used by every module in zalo-service."""
    return _build_logger(name)
