"""Tests for :mod:`fluxlit.logging` JSON formatter."""

from __future__ import annotations

import io
import json
import logging
import sys
from datetime import date, datetime, timezone

from fluxlit.logging.json_formatter import JsonLogFormatter


def test_json_log_formatter_includes_extra_fields() -> None:
    fmt = JsonLogFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="x.py",
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    record.request_id = "abc-123"
    record.fluxlit_dispatch = "streamlit"
    line = fmt.format(record)
    data = json.loads(line)
    assert data["message"] == "hello world"
    assert data["level"] == "INFO"
    assert data["logger"] == "test"
    assert data["request_id"] == "abc-123"
    assert data["fluxlit_dispatch"] == "streamlit"


def test_json_log_formatter_includes_exception_block() -> None:
    fmt = JsonLogFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        exc = sys.exc_info()
        record = logging.LogRecord(
            name="x",
            level=logging.ERROR,
            pathname="x.py",
            lineno=1,
            msg="failed",
            args=(),
            exc_info=exc,
        )
    line = fmt.format(record)
    data = json.loads(line)
    assert data["level"] == "ERROR"
    assert "exception" in data
    assert "ValueError: boom" in data["exception"]


def test_json_log_formatter_serializes_datetime_and_bytes() -> None:
    fmt = JsonLogFormatter()
    dt = datetime(2024, 3, 15, 12, 30, tzinfo=timezone.utc)
    record = logging.LogRecord(
        name="t",
        level=logging.INFO,
        pathname="x.py",
        lineno=1,
        msg="m",
        args=(),
        exc_info=None,
    )
    record.at = dt
    record.raw = b"\xff\xfe"
    line = fmt.format(record)
    data = json.loads(line)
    assert data["at"] == dt.isoformat()
    assert data["raw"] == "\ufffd\ufffd"


def test_json_log_formatter_serializes_date_and_arbitrary_object() -> None:
    fmt = JsonLogFormatter()
    record = logging.LogRecord(
        name="t",
        level=logging.INFO,
        pathname="x.py",
        lineno=1,
        msg="m",
        args=(),
        exc_info=None,
    )
    record.d = date(2024, 1, 2)
    record.obj = object()
    line = fmt.format(record)
    data = json.loads(line)
    assert data["d"] == "2024-01-02"
    assert data["obj"].startswith("<object object at")


def test_json_formatter_stream_handler_roundtrip() -> None:
    """Same wiring as ``dictConfig`` examples: handler + :class:`JsonLogFormatter`."""
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(JsonLogFormatter())
    log = logging.getLogger("fluxlit_json_roundtrip_test")
    log.handlers.clear()
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.propagate = False
    try:
        log.info("hello handler", extra={"request_id": "rid-7"})
        line = buf.getvalue().strip()
        data = json.loads(line)
        assert data["message"] == "hello handler"
        assert data["request_id"] == "rid-7"
    finally:
        log.removeHandler(handler)
