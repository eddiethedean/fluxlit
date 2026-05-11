from __future__ import annotations

from fluxlit.logging.redact import (
    redact_authorization,
    redact_query_string,
    sanitize_headers,
)


def test_redact_bearer() -> None:
    assert redact_authorization("Bearer secret-token") == "Bearer <redacted>"


def test_sanitize_headers_never_echoes_bearer_secret() -> None:
    secret = "super-secret-value-xyz"
    out = sanitize_headers({"Authorization": f"Bearer {secret}", "X-Other": "ok"})
    assert secret not in out["Authorization"]
    assert "<redacted>" in out["Authorization"]
    assert out["X-Other"] == "ok"


def test_sanitize_headers_redacts_cookie() -> None:
    out = sanitize_headers({"Cookie": "session=abc123"})
    assert out["Cookie"] == "<redacted>"


def test_redact_basic_auth() -> None:
    assert "secret" not in redact_authorization("Basic c2VjcmV0").lower()


def test_redact_non_bearer_is_placeholder() -> None:
    assert redact_authorization("Custom tok") == "<redacted>"


def test_sanitize_headers_case_insensitive_authorization() -> None:
    secret = "nope"
    out = sanitize_headers({"authorization": f"Bearer {secret}"})
    assert secret not in out["authorization"]


def test_sanitize_headers_non_string_values() -> None:
    out = sanitize_headers({"Authorization": "Bearer x", "X-Int": 1})  # type: ignore[arg-type]
    assert out["X-Int"] == "1"


def test_redact_query_string_fluxlit_sid() -> None:
    out = redact_query_string("fluxlit_sid=secret123&foo=bar")
    assert "secret123" not in out
    assert "redacted" in out.lower()
    assert "foo" in out and "bar" in out


def test_redact_query_string_custom_key() -> None:
    out = redact_query_string("my_sid=abc&x=1", sensitive_keys=frozenset({"my_sid"}))
    assert "abc" not in out
    assert "redacted" in out.lower()


def test_sanitize_headers_preserves_unlisted_headers() -> None:
    out = sanitize_headers({"X-Api-Key": "public-id", "Authorization": "Bearer z"})
    assert out["X-Api-Key"] == "public-id"
