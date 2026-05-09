"""Streamlit helpers for FluxLit BFF auth (query-param auth code exchange)."""

from __future__ import annotations

from typing import Any

from fluxlit.client import ApiClient


def _query_param_raw(query_params: Any, key: str) -> str | None:
    raw = query_params.get(key) if hasattr(query_params, "get") else None
    if raw is None:
        return None
    if isinstance(raw, list):
        return str(raw[0]) if raw else None
    return str(raw)


def exchange_auth_code_from_query(
    st_module: Any,
    client: ApiClient,
    *,
    exchange_path: str = "/auth/exchange",
    query_key: str = "auth_code",
    session_key: str = "fluxlit_access_token",
) -> str | None:
    """If ``query_key`` is present, exchange it for an access token and store in session.

    Returns the access token when exchanged; otherwise ``None``. On HTTP errors from
    the exchange endpoint, raises :class:`httpx.HTTPStatusError`.

    Typical usage at the top of a page::

        exchange_auth_code_from_query(st, client)
        token = st.session_state.get(\"fluxlit_access_token\")
    """
    code = _query_param_raw(st_module.query_params, query_key)
    if not code:
        return None
    response = client.post(exchange_path, json={"code": code})
    response.raise_for_status()
    data = response.json()
    token = data.get("access_token")
    if not isinstance(token, str) or not token:
        raise ValueError("Exchange response missing access_token")
    st_module.session_state[session_key] = token
    if hasattr(st_module.query_params, "pop"):
        try:
            st_module.query_params.pop(query_key)
        except Exception:
            pass
    return token


def bearer_headers_from_session(
    st_module: Any,
    *,
    session_key: str = "fluxlit_access_token",
) -> dict[str, str]:
    """Build ``Authorization`` headers from ``st.session_state`` (no logging of secrets)."""
    token = st_module.session_state.get(session_key)
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}
