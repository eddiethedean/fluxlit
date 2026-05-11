"""Helpers to redact secrets from header dicts before logging or tracing."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qsl, urlencode

# URL-bound session continuity (see :mod:`fluxlit.url_session`) and other
# sensitive query keys to strip from gateway access logs.
DEFAULT_SENSITIVE_QUERY_KEYS: frozenset[str] = frozenset({"fluxlit_sid"})


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


def redact_query_string(
    query_string: str,
    *,
    sensitive_keys: frozenset[str] | None = None,
) -> str:
    """Return *query_string* with listed keys' values replaced by ``<redacted>``.

    *query_string* is the raw ``key=value&...`` portion (no leading ``?``).
    Unknown or malformed segments are returned unchanged when parsing fails.
    """
    if not query_string:
        return ""
    keys = sensitive_keys or DEFAULT_SENSITIVE_QUERY_KEYS
    try:
        pairs = parse_qsl(query_string, keep_blank_values=True, strict_parsing=False)
    except Exception:
        return query_string
    out: list[tuple[str, str]] = []
    for k, v in pairs:
        if k in keys and v:
            out.append((k, "<redacted>"))
        else:
            out.append((k, v))
    return urlencode(out)
