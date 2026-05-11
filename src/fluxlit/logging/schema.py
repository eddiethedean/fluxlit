"""Documented logging field contracts."""

from __future__ import annotations

JSON_LOG_BASE_FIELDS: tuple[str, ...] = ("time", "level", "logger", "message")
GATEWAY_ACCESS_LOG_FIELDS: tuple[str, ...] = (
    "request_id",
    "fluxlit_dispatch",
    "http_method_or_type",
    "path",
    "query",
)
