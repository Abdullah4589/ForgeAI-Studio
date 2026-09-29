"""Structured JSON logging using only the standard library."""

import json
import logging
from datetime import UTC, datetime
from typing import Any

# Attributes present on every LogRecord; anything else came from `extra=` (structured data).
_RESERVED = set(vars(logging.makeLogRecord({}))) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        for key, value in vars(record).items():
            if key not in _RESERVED:
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    # Uvicorn's access log duplicates our request info and isn't JSON; keep it quieter.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def truncate(text: str, limit: int = 80) -> str:
    """Prompts can be long or personal; logs only need enough to correlate."""
    return text if len(text) <= limit else text[:limit] + "…"
