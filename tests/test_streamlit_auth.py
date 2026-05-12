from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from fluxlit.auth.streamlit import (
    bearer_headers_from_session,
    exchange_auth_code_from_query,
    prepare_streamlit_api_client,
)
from fluxlit.client import ApiClient


def test_query_param_raw_list_and_string() -> None:
    from fluxlit.auth.streamlit import _query_param_raw

    assert _query_param_raw({"k": ["a", "b"]}, "k") == "a"
    assert _query_param_raw({"k": []}, "k") is None
    assert _query_param_raw({"k": "x"}, "k") == "x"
    assert _query_param_raw({"k": None}, "k") is None


def test_exchange_auth_code_returns_none_without_param(monkeypatch: pytest.MonkeyPatch) -> None:
    st = MagicMock()
    st.query_params = {}
    st.session_state = {}
    monkeypatch.delenv("FLUXLIT_INTERNAL_API_BASE", raising=False)
    assert (
        exchange_auth_code_from_query(st, ApiClient(base_url="http://127.0.0.1:8000/api")) is None
    )


def test_exchange_auth_code_posts_and_stores_session(monkeypatch: pytest.MonkeyPatch) -> None:
    st = MagicMock()
    st.query_params = {"auth_code": "onetimelongcodevalue"}
    st.session_state = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/auth/exchange")
        return httpx.Response(200, json={"access_token": "tok-abc", "token_type": "bearer"})

    transport = httpx.MockTransport(handler)
    monkeypatch.delenv("FLUXLIT_INTERNAL_API_BASE", raising=False)
    client = ApiClient(base_url="http://127.0.0.1:8000/api")
    client._client = httpx.Client(base_url=client._client.base_url, transport=transport)
    token = exchange_auth_code_from_query(st, client, exchange_path="/auth/exchange")
    assert token == "tok-abc"
    assert st.session_state["fluxlit_access_token"] == "tok-abc"


def test_exchange_auth_code_raises_when_no_access_token_in_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    st = MagicMock()
    st.query_params = {"auth_code": "longenough"}
    st.session_state = {}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": True})

    transport = httpx.MockTransport(handler)
    monkeypatch.delenv("FLUXLIT_INTERNAL_API_BASE", raising=False)
    client = ApiClient(base_url="http://127.0.0.1:8000/api")
    client._client = httpx.Client(base_url=client._client.base_url, transport=transport)
    with pytest.raises(ValueError, match="access_token"):
        exchange_auth_code_from_query(st, client)


def test_exchange_auth_code_propagates_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    st = MagicMock()
    st.query_params = {"auth_code": "longenough"}
    st.session_state = {}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "nope"})

    transport = httpx.MockTransport(handler)
    monkeypatch.delenv("FLUXLIT_INTERNAL_API_BASE", raising=False)
    client = ApiClient(base_url="http://127.0.0.1:8000/api")
    client._client = httpx.Client(base_url=client._client.base_url, transport=transport)
    with pytest.raises(httpx.HTTPStatusError):
        exchange_auth_code_from_query(st, client)


def test_exchange_auth_code_swallows_query_pop_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    st = MagicMock()
    st.query_params = MagicMock()
    st.query_params.get.return_value = "longenough"
    st.query_params.pop.side_effect = RuntimeError("read-only")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"access_token": "ok", "token_type": "bearer"})

    transport = httpx.MockTransport(handler)
    monkeypatch.delenv("FLUXLIT_INTERNAL_API_BASE", raising=False)
    client = ApiClient(base_url="http://127.0.0.1:8000/api")
    client._client = httpx.Client(base_url=client._client.base_url, transport=transport)
    assert exchange_auth_code_from_query(st, client) == "ok"


def test_exchange_auth_code_pop_failure_logs_when_debug(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("FLUXLIT_DEBUG", "1")
    st = MagicMock()
    st.query_params = MagicMock()
    st.query_params.get.return_value = "longenough"
    st.query_params.pop.side_effect = RuntimeError("read-only")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"access_token": "ok", "token_type": "bearer"})

    transport = httpx.MockTransport(handler)
    monkeypatch.delenv("FLUXLIT_INTERNAL_API_BASE", raising=False)
    client = ApiClient(base_url="http://127.0.0.1:8000/api")
    client._client = httpx.Client(base_url=client._client.base_url, transport=transport)
    caplog.set_level(10, logger="fluxlit.auth.streamlit")
    assert exchange_auth_code_from_query(st, client) == "ok"
    assert any("query_params.pop" in rec.message for rec in caplog.records)


def test_bearer_headers_from_session_empty_and_set() -> None:
    st = MagicMock()
    st.session_state = {}
    assert bearer_headers_from_session(st) == {}
    st.session_state["fluxlit_access_token"] = "secret"
    assert bearer_headers_from_session(st) == {"Authorization": "Bearer secret"}
    assert bearer_headers_from_session(st, session_key="other") == {}


def test_prepare_streamlit_api_client_skips_exchange_when_session_has_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Existing session token must not call exchange_auth_code_from_query."""
    calls: list[object] = []

    def spy(*_a: object, **_k: object) -> None:
        calls.append(True)

    monkeypatch.setattr("fluxlit.auth.streamlit.exchange_auth_code_from_query", spy)
    monkeypatch.delenv("FLUXLIT_INTERNAL_API_BASE", raising=False)
    st = MagicMock()
    st.session_state = {"fluxlit_access_token": "cached"}
    st.query_params = {"auth_code": "ignored"}
    api = prepare_streamlit_api_client(st, base_url="http://127.0.0.1:8000/api")
    try:
        assert calls == []
        assert st.session_state["fluxlit_access_token"] == "cached"
    finally:
        api.close()


def test_prepare_streamlit_api_client_returns_bootstrap_when_no_code_no_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FLUXLIT_INTERNAL_API_BASE", raising=False)
    st = MagicMock()
    st.session_state = {}
    st.query_params = {}
    api = prepare_streamlit_api_client(st, base_url="http://127.0.0.1:8000/api")
    try:
        assert api._auth_header_factory is None  # type: ignore[attr-defined]
        assert st.session_state.get("fluxlit_access_token") is None
    finally:
        api.close()


def test_prepare_streamlit_api_client_exchange_then_sends_bearer_on_get(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After auth_code exchange, follow-up GET must include Authorization (bootstrap closed)."""
    monkeypatch.delenv("FLUXLIT_INTERNAL_API_BASE", raising=False)
    st = MagicMock()
    st.session_state = {}
    st.query_params = {"auth_code": "longenoughcodeherexxx"}
    auth_on_requests: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        auth_on_requests.append(request.headers.get("authorization"))
        if request.url.path.endswith("/auth/exchange"):
            body = {"access_token": "after-exchange", "token_type": "bearer"}
            return httpx.Response(200, json=body)
        return httpx.Response(200, json={"status": "ok"})

    transport = httpx.MockTransport(handler)
    orig_client = httpx.Client

    def client_factory(**kwargs: object) -> httpx.Client:
        merged = dict(kwargs)
        merged["transport"] = transport
        return orig_client(**merged)

    monkeypatch.setattr("fluxlit.client.httpx.Client", client_factory)
    api = prepare_streamlit_api_client(st, base_url="http://127.0.0.1:8000/api")
    try:
        api.get("/protected")
    finally:
        api.close()
    assert st.session_state["fluxlit_access_token"] == "after-exchange"
    assert auth_on_requests[0] is None
    assert auth_on_requests[1] == "Bearer after-exchange"
