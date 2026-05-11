"""Helpers to redact secrets from header dicts before logging or tracing."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def redact_authorization(value: str) -> str:
    """Return a placeholder for an ``Authorization`` header value."""
    s = (value or "").strip()
    if not s:
        return ""
    lower = s.lower()
    if lower.startswith("bearer "):
        return "Bearer <redacted>"
    if lower.startswith("basic "):
        return "Basic <redacted>"
    return "<redacted>"


def sanitize_headers(headers: Mapping[str, Any]) -> dict[str, str]:
    """Copy *headers* with ``Authorization`` and ``Cookie`` values redacted."""
    out: dict[str, str] = {}
    for k, v in headers.items():
        lk = str(k).lower()
        raw = v if isinstance(v, str) else str(v)
        if lk == "authorization":
            out[str(k)] = redact_authorization(raw)
        elif lk == "cookie":
            out[str(k)] = "<redacted>"
        else:
            out[str(k)] = raw
    return out
