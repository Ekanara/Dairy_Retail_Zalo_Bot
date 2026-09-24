"""
Structured JSON logger for models-service.

Every log record is emitted as a single-line JSON object so it can be
ingested by any log-aggregation stack (Loki, ELK, CloudWatch …).

Schema
------
{
  "timestamp": "<ISO-8601 with TZ>",
  "level":     "INFO",
  "service":   "models-service",
  "event":     "<event_name>",
  "user_id":   "<zalo_user_id | null>",
  "model":     "<model_name | null>",
  "latency_ms": <int | null>,
  "token_count": <int | null>,
  ...extra fields...
}
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


# ── ANSI colour helpers (only when stderr is a TTY) ──────────────────────────
_COLOURS = {
    "DEBUG": "\033[36m",     # cyan
    "INFO": "\033[32m",      # green
    "WARNING": "\033[33m",   # yellow
    "ERROR": "\033[31m",     # red
    "CRITICAL": "\033[35m",  # magenta
    "RESET": "\033[0m",
    "SKILL": "\033[34m",     # blue — for skill tool calls
}
_USE_COLOURS = True  # Always emit ANSI colours — viewable via `tail -f` in a TTY


class _JSONFormatter(logging.Formatter):
    """Formats every LogRecord as a single-line JSON object."""

    SERVICE = "models-service"

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        # ── Base payload ──────────────────────────────────────────────
        payload: dict[str, Any] = {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "service": self.SERVICE,
            "event": record.getMessage(),
        }

        # ── Structured extras passed via `extra={...}` ───────────────
        _skip = {
            "name", "msg", "args", "levelname", "levelno", "pathname",
            "filename", "module", "exc_info", "exc_text", "stack_info",
            "lineno", "funcName", "created", "msecs", "relativeCreated",
            "thread", "threadName", "processName", "process", "message",
            "taskName",
        }
        for key, val in record.__dict__.items():
            if key not in _skip:
                payload[key] = val

        # ── Exception chain (if any) ──────────────────────────────────
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        line = json.dumps(payload, ensure_ascii=False, default=str)

        if _USE_COLOURS:
            # Use blue for skill-related events, otherwise level-based colour
            event_str = str(payload.get("event", ""))
            if "skill" in event_str.lower():
                colour = _COLOURS["SKILL"]
            else:
                colour = _COLOURS.get(record.levelname, "")
            reset = _COLOURS["RESET"]
            line = f"{colour}{line}{reset}"

        return line


class _ContextLogger(logging.LoggerAdapter):
    """
    Thin wrapper that lets callers pass structured fields as kwargs:

        logger.info("chat_completed", user_id="x", latency_ms=12)

    All kwargs are forwarded into `extra` so they appear in the JSON.
    This maintains backward compatibility with code that uses extra={}.
    """

    def process(
        self, msg: str, kwargs: dict[str, Any]
    ) -> tuple[str, dict[str, Any]]:
        extra = dict(self.extra or {})
        # If 'extra' key exists in kwargs, merge it
        if "extra" in kwargs:
            extra.update(kwargs.pop("extra"))
        # Pull structured fields out of kwargs into extra
        for key in list(kwargs.keys()):
            if key not in ("exc_info", "stack_info", "stacklevel"):
                extra[key] = kwargs.pop(key)
        kwargs["extra"] = extra
        return msg, kwargs


def _build_logger(name: str, level: str = "INFO") -> _ContextLogger:
    raw = logging.getLogger(name)
    if not raw.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_JSONFormatter())
        raw.addHandler(handler)
    raw.setLevel(getattr(logging, level.upper(), logging.INFO))
    raw.propagate = False
    return _ContextLogger(raw, {})


def get_logger(name: str = "models-service") -> _ContextLogger:
    """
    Return (and cache) a structured JSON logger.

    Usage
    -----
    # Both syntaxes are supported:
    logger.info("chat_completed", extra={"user_id": uid, "latency_ms": 340})
    logger.info("chat_completed", user_id=uid, latency_ms=340)
    """
    from app.core.config import settings  # late import — avoids circular dep

    return _build_logger(name, level=settings.LOG_LEVEL)
