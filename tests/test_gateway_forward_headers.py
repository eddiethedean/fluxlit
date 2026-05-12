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


def test_normalize_dedupes_case_variants() -> None:
    n = normalize_gateway_forward_header_allowlist(["Traceparent", "traceparent", "X-Req"])
    assert n == frozenset({"traceparent", "x-req"})


def test_normalize_rejects_invalid_token_shapes() -> None:
    assert normalize_gateway_forward_header_allowlist(["-bad", "bad..name", ""]) == frozenset()


def test_normalize_accepts_max_length_token() -> None:
    # One [a-z0-9] + 63 [a-z0-9-] = 64 chars total (regex upper bound).
    token = "a" + ("b" * 63)
    assert len(token) == 64
    n = normalize_gateway_forward_header_allowlist([token])
    assert n == frozenset({token})


def test_normalize_rejects_overlong_token() -> None:
    token = "a" * 65
    assert normalize_gateway_forward_header_allowlist([token]) == frozenset()


def test_merge_allowlisted_last_raw_value_wins() -> None:
    h = httpx.Headers()
    raw = [
        (b"traceparent", b"00-first"),
        (b"Traceparent", b"00-second"),
    ]
    merge_allowlisted_browser_headers(h, raw, frozenset({"traceparent"}))
    assert h.get("traceparent") == "00-second"


def test_merge_allowlisted_preserves_non_ascii_latin1_values() -> None:
    h = httpx.Headers()
    raw = [(b"x-correlation-id", b"abc\xff")]
    merge_allowlisted_browser_headers(h, raw, frozenset({"x-correlation-id"}))
    assert h.get("x-correlation-id") == "abc\xff"


def test_merge_empty_allowlist_does_not_touch_headers() -> None:
    h = httpx.Headers([("host", "upstream")])
    merge_allowlisted_browser_headers(
        h,
        [(b"traceparent", b"00-should-not-appear")],
        frozenset(),
    )
    assert h.get("traceparent") is None
    assert h.get("host") == "upstream"
