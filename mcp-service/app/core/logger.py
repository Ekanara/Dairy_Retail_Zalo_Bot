import logging
import json
import time
from typing import Any


class _JSONFormatter(logging.Formatter):
    """Formatter ghi mỗi log record thành 1 dòng JSON."""

    SERVICE = "mcp-service"

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "service": self.SERVICE,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Gộp extra fields (tool_name, user_id, duration_ms, result_count …)
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "levelname", "levelno",
                "pathname", "filename", "module", "exc_info", "exc_text",
                "stack_info", "lineno", "funcName", "created", "msecs",
                "relativeCreated", "thread", "threadName", "processName",
                "process", "message", "taskName",
            }:
                payload[key] = value

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def get_logger(name: str) -> logging.Logger:
    """Trả về logger JSON đã cấu hình, dùng chung toàn service."""
    from app.core.config import settings  # import muộn tránh circular

    logger = logging.getLogger(name)
    if logger.handlers:
        # Đã cấu hình — trả về luôn để tránh duplicate handlers
        return logger

    handler = logging.StreamHandler()
    handler.setFormatter(_JSONFormatter())
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
    logger.propagate = False
    return logger
