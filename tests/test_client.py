from __future__ import annotations

import httpx
import pytest
from pydantic import BaseModel, ValidationError

from fluxlit.client import ApiClient


class _User(BaseModel):
    name: str


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


def test_api_client_merges_auth_factory_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLUXLIT_INTERNAL_API_BASE", raising=False)
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(dict(request.headers))
        return httpx.Response(200)

    transport = httpx.MockTransport(handler)
    with ApiClient(
        base_url="http://127.0.0.1:8000/api",
        auth_header_factory=lambda: {"Authorization": "Bearer secret"},
    ) as client:
        client._client = httpx.Client(base_url=client._client.base_url, transport=transport)
        client.get("/ping")
    assert captured.get("authorization") == "Bearer secret"


def test_api_client_for_fluxlit_rejects_both_factory_and_token() -> None:
    with pytest.raises(TypeError, match="only one"):
        ApiClient.for_fluxlit(bearer_token="a", auth_header_factory=lambda: {})


def test_api_client_propagates_request_id_when_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FLUXLIT_INTERNAL_API_BASE", raising=False)
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(dict(request.headers))
        return httpx.Response(200)

    transport = httpx.MockTransport(handler)
    from fluxlit.logging_context import REQUEST_ID_HEADER, set_request_id

    token = set_request_id("req-xyz")
    try:
        with ApiClient(
            base_url="http://127.0.0.1:8000/api",
            propagate_request_id=True,
        ) as client:
            client._client = httpx.Client(base_url=client._client.base_url, transport=transport)
            client.get("/ping")
    finally:
        from fluxlit.logging_context import reset_request_id

        reset_request_id(token)
    assert captured.get(REQUEST_ID_HEADER) == "req-xyz"


def test_api_client_default_headers_merged_and_overridden(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLUXLIT_INTERNAL_API_BASE", raising=False)
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update({k.lower(): v for k, v in request.headers.items()})
        return httpx.Response(200)

    transport = httpx.MockTransport(handler)
    with ApiClient(
        base_url="http://127.0.0.1:8000/api",
        default_headers={"X-App": "1", "X-Shared": "from-default"},
    ) as client:
        client._client = httpx.Client(base_url=client._client.base_url, transport=transport)
        client.get("/r", headers={"X-Shared": "from-call"})
    assert captured.get("x-app") == "1"
    assert captured.get("x-shared") == "from-call"


def test_api_client_for_fluxlit_bearer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLUXLIT_INTERNAL_API_BASE", raising=False)
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(dict(request.headers))
        return httpx.Response(200)

    transport = httpx.MockTransport(handler)
    with ApiClient.for_fluxlit(bearer_token="tok", base_url="http://127.0.0.1:8000/api") as client:
        client._client = httpx.Client(base_url=client._client.base_url, transport=transport)
        client.get("/x")
    assert captured.get("authorization") == "Bearer tok"


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

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/users"
        return httpx.Response(200)

    transport = httpx.MockTransport(handler)
    client._client = httpx.Client(base_url=client._client.base_url, transport=transport)
    client.get("users")


def test_get_model_parses_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLUXLIT_INTERNAL_API_BASE", raising=False)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"name": "Ada"})

    transport = httpx.MockTransport(handler)
    with ApiClient(base_url="http://127.0.0.1:8000/api") as client:
        client._client = httpx.Client(base_url=client._client.base_url, transport=transport)
        user = client.get_model("/users", _User)
    assert user.name == "Ada"


def test_post_model_parses_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLUXLIT_INTERNAL_API_BASE", raising=False)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        return httpx.Response(200, json={"name": "Bob"})

    transport = httpx.MockTransport(handler)
    with ApiClient(base_url="http://127.0.0.1:8000/api") as client:
        client._client = httpx.Client(base_url=client._client.base_url, transport=transport)
        user = client.post_model("/users", _User, body={"name": "ignored"})
    assert user.name == "Bob"


def test_get_model_raises_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLUXLIT_INTERNAL_API_BASE", raising=False)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "missing"})

    transport = httpx.MockTransport(handler)
    with ApiClient(base_url="http://127.0.0.1:8000/api") as client:
        client._client = httpx.Client(base_url=client._client.base_url, transport=transport)
        with pytest.raises(httpx.HTTPStatusError):
            client.get_model("/nope", _User)


def test_get_model_raises_validation_error_on_bad_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLUXLIT_INTERNAL_API_BASE", raising=False)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"not_name": "x"})

    transport = httpx.MockTransport(handler)
    with ApiClient(base_url="http://127.0.0.1:8000/api") as client:
        client._client = httpx.Client(base_url=client._client.base_url, transport=transport)
        with pytest.raises(ValidationError):
            client.get_model("/users", _User)


def test_put_delete_requests_use_correct_method(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLUXLIT_INTERNAL_API_BASE", raising=False)
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.method)
        return httpx.Response(204)

    transport = httpx.MockTransport(handler)
    with ApiClient(base_url="http://127.0.0.1:8000/api") as client:
        client._client = httpx.Client(base_url=client._client.base_url, transport=transport)
        client.put("items/1", json={"a": 1})
        client.delete("items/1")
    assert seen == ["PUT", "DELETE"]


def test_post_model_raises_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLUXLIT_INTERNAL_API_BASE", raising=False)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"detail": []})

    transport = httpx.MockTransport(handler)
    with ApiClient(base_url="http://127.0.0.1:8000/api") as client:
        client._client = httpx.Client(base_url=client._client.base_url, transport=transport)
        with pytest.raises(httpx.HTTPStatusError):
            client.post_model("/users", _User, body={})
