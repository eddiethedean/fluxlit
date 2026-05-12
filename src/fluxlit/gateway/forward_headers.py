"""Optional allowlisted forwarding of browser headers on the gateway → Streamlit HTTP hop."""

from __future__ import annotations

import re
from collections.abc import Iterable

import httpx

# Never forward these to Streamlit on the HTTP proxy hop (case-insensitive names).
_FORWARD_HTTP_BLOCKLIST = frozenset(
    {
        "authorization",
        "cookie",
        "set-cookie",
        "proxy-authorization",
        "host",
        "connection",
        "content-length",
        "transfer-encoding",
        "te",
        "upgrade",
        "keep-alive",
        "proxy-connection",
        "x-forwarded-for",
        "x-forwarded-host",
        "x-forwarded-proto",
        "x-forwarded-port",
        "x-forwarded-prefix",
    }
)

_HEADER_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def normalize_gateway_forward_header_allowlist(names: Iterable[str]) -> frozenset[str]:
    """Lower-case unique names; drop empty, invalid, and blocklisted tokens."""
    out: set[str] = set()
    for raw in names:
        n = (raw or "").strip().lower()
        if not n or n in _FORWARD_HTTP_BLOCKLIST:
            continue
        if not _HEADER_NAME_RE.match(n):
            continue
        out.add(n)
    return frozenset(out)


def merge_allowlisted_browser_headers(
    headers: httpx.Headers,
    raw_scope_headers: list[tuple[bytes, bytes]],
    allowlist: frozenset[str],
) -> None:
    """Copy allowlisted client header lines onto *headers* (last write wins).

    Expects *raw_scope_headers* as in the ASGI scope (bytes pairs). Only names present
    in *allowlist* are merged; hop-by-hop and forwarding headers should stay out of the
    allowlist (they are also rejected in :func:`normalize_gateway_forward_header_allowlist`).
    """
    if not allowlist:
        return
    for k, v in raw_scope_headers:
        key = k.decode("latin-1")
        lk = key.lower()
        if lk not in allowlist:
            continue
        if lk in _FORWARD_HTTP_BLOCKLIST:
            continue
        val = v.decode("latin-1")
        headers[key] = val
