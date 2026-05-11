"""Logging helpers: request IDs, JSON formatters, redaction for safe access logs."""

from fluxlit.logging.context import (
    REQUEST_ID_HEADER,
    get_request_id,
    log,
    new_request_id,
    request_id_ctx,
    reset_request_id,
    set_request_id,
)
from fluxlit.logging.json_formatter import JsonLogFormatter
from fluxlit.logging.redact import (
    DEFAULT_SENSITIVE_QUERY_KEYS,
    redact_authorization,
    redact_query_string,
    sanitize_headers,
)
from fluxlit.logging.schema import GATEWAY_ACCESS_LOG_FIELDS, JSON_LOG_BASE_FIELDS

__all__ = [
    "DEFAULT_SENSITIVE_QUERY_KEYS",
    "GATEWAY_ACCESS_LOG_FIELDS",
    "JsonLogFormatter",
    "JSON_LOG_BASE_FIELDS",
    "REQUEST_ID_HEADER",
    "get_request_id",
    "log",
    "new_request_id",
    "redact_authorization",
    "redact_query_string",
    "request_id_ctx",
    "reset_request_id",
    "sanitize_headers",
    "set_request_id",
]
