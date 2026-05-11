"""Optional JSON :class:`logging.Formatter` for one-line structured logs (stdlib only)."""

from __future__ import annotations

import json
import logging
import numbers
from datetime import date, datetime
from typing import Any

_LOG_RECORD_RESERVED: frozenset[str] = frozenset(
    {
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
)


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, numbers.Number)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, BaseException):
        return repr(value)
    return repr(value)


class JsonLogFormatter(logging.Formatter):
    """Emit one JSON object per log line, including merged ``extra`` fields."""

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        payload: dict[str, Any] = {
            "time": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": message,
        }
        for key, raw in record.__dict__.items():
            if key in _LOG_RECORD_RESERVED or key.startswith("_"):
                continue
            payload[key] = _json_safe(raw)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)
