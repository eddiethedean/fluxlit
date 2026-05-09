from __future__ import annotations

import httpx
import pytest

from fluxlit.client import ApiClient


def test_api_client_uses_explicit_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLUXLIT_INTERNAL_API_BASE", raising=False)
    with ApiClient(base_url="http://example.com/api") as c:
        assert str(c._client.base_url) in {"http://example.com/api", "http://example.com/api/"}


def test_api_client_uses_env_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLUXLIT_INTERNAL_API_BASE", "http://127.0.0.1:9999/api/")
    with ApiClient() as c:
        assert str(c._client.base_url) in {
            "http://127.0.0.1:9999/api",
            "http://127.0.0.1:9999/api/",
        }


def test_api_client_default_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLUXLIT_INTERNAL_API_BASE", raising=False)
    with ApiClient() as c:
        assert str(c._client.base_url) in {
            "http://127.0.0.1:8000/api",
            "http://127.0.0.1:8000/api/",
        }


def test_api_client_adds_leading_slash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLUXLIT_INTERNAL_API_BASE", raising=False)
    client = ApiClient(base_url="http://127.0.0.1:8000/api")

    captured = {}

    def fake_request(method: str, url: str, **kwargs: object) -> httpx.Response:
        captured["method"] = method
        captured["url"] = url
        return httpx.Response(200)

    client._client.request = fake_request  # type: ignore[method-assign]
    client.get("users")
    assert captured["url"] == "/users"
