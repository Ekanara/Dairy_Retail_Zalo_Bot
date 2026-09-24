import logging
import json
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Emit every log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        log: dict = {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "service": "data-service",
            "event": record.getMessage(),
        }
        # Merge any structured fields attached via the `extra` kwarg
        if hasattr(record, "extra"):
            log.update(record.extra)
        # Forward exc_info when present so errors are never silent
        if record.exc_info:
            log["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log, ensure_ascii=False)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
    logger.propagate = False
    logger.setLevel(logging.INFO)
    return logger
