"""Unit tests for :mod:`fluxlit.gateway.forward_headers`."""

from __future__ import annotations

import httpx

from fluxlit.gateway.forward_headers import (
    merge_allowlisted_browser_headers,
    normalize_gateway_forward_header_allowlist,
)


def test_normalize_drops_secrets_and_invalid() -> None:
    n = normalize_gateway_forward_header_allowlist(
        ["X-Request-ID", "authorization", "traceparent", "", "bad name", "cookie"]
    )
    assert n == frozenset({"x-request-id", "traceparent"})


def test_merge_allowlisted_sets_matching_headers() -> None:
    h = httpx.Headers()
    raw = [
        (b"Traceparent", b"00-abc-def-01"),
        (b"Cookie", b"sid=1"),
        (b"X-Custom-Thing", b"yes"),
    ]
    merge_allowlisted_browser_headers(h, raw, frozenset({"traceparent", "x-custom-thing"}))
    assert h.get("traceparent") == "00-abc-def-01"
    assert h.get("cookie") is None


def test_merge_allowlisted_skips_blocklisted_even_if_allowlist_contains_it() -> None:
    h = httpx.Headers()
    merge_allowlisted_browser_headers(h, [(b"Cookie", b"secret")], frozenset({"cookie"}))
    assert h.get("cookie") is None
