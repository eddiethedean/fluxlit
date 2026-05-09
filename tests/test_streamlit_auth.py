from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from fluxlit.client import ApiClient
from fluxlit.streamlit_auth import (
    bearer_headers_from_session,
    exchange_auth_code_from_query,
)


def test_query_param_raw_list_and_string() -> None:
    from fluxlit.streamlit_auth import _query_param_raw

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


def test_bearer_headers_from_session_empty_and_set() -> None:
    st = MagicMock()
    st.session_state = {}
    assert bearer_headers_from_session(st) == {}
    st.session_state["fluxlit_access_token"] = "secret"
    assert bearer_headers_from_session(st) == {"Authorization": "Bearer secret"}
    assert bearer_headers_from_session(st, session_key="other") == {}
