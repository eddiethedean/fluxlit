from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
from starlette.testclient import TestClient

from fluxlit import FluxLit
from fluxlit.auth.jwt import JWTBearer
from fluxlit.auth.oidc import GenericOIDCClient, GenericOIDCClientConfig
from fluxlit.auth.streamlit import prepare_streamlit_api_client
from fluxlit.config import FluxlitSettings


def test_jwt_bearer_from_fluxlit_settings_hs256() -> None:
    s = FluxlitSettings(
        jwt_issuer="https://iss",
        jwt_audience="aud",
        jwt_hs256_secret="x" * 32,
    )
    b = JWTBearer.from_fluxlit_settings(s)
    assert isinstance(b, JWTBearer)


def test_jwt_bearer_from_settings_rejects_both_secret_and_jwks() -> None:
    s = FluxlitSettings(
        jwt_issuer="i",
        jwt_audience="a",
        jwt_hs256_secret="s" * 32,
        jwt_jwks_url="https://j/jwks",
    )
    with pytest.raises(ValueError, match="only one"):
        JWTBearer.from_fluxlit_settings(s)


def test_jwt_bearer_from_settings_requires_issuer_audience() -> None:
    with pytest.raises(ValueError, match="JWT_ISSUER"):
        JWTBearer.from_fluxlit_settings(
            FluxlitSettings(jwt_hs256_secret="y" * 32),
        )


def test_flux_lit_make_jwt_bearer() -> None:
    app = FluxLit(
        settings=FluxlitSettings(
            jwt_issuer="https://iss",
            jwt_audience="aud",
            jwt_hs256_secret="z" * 32,
        )
    )
    assert isinstance(app.make_jwt_bearer(), JWTBearer)


def test_flux_lit_attach_oidc_login_requires_secret() -> None:
    oidc = GenericOIDCClient(
        GenericOIDCClientConfig(issuer="https://x", client_id="a", client_secret="b")
    )
    app = FluxLit(settings=FluxlitSettings(oidc_bff_secret=""))
    with pytest.raises(ValueError, match="OIDC BFF"):
        app.attach_oidc_login(oidc)


def test_flux_lit_attach_oidc_login_rejects_second_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(GenericOIDCClient, "load_discovery_sync", lambda self: None)
    from fluxlit.auth.oidc import OIDCDiscoveryDocument

    oidc = GenericOIDCClient(
        GenericOIDCClientConfig(issuer="https://idp", client_id="c", client_secret="d")
    )
    oidc._doc = OIDCDiscoveryDocument.model_validate(  # noqa: SLF001
        {
            "issuer": "https://idp",
            "authorization_endpoint": "https://idp/a",
            "token_endpoint": "https://idp/t",
            "jwks_uri": "https://idp/j",
        }
    )
    app = FluxLit(
        settings=FluxlitSettings(oidc_bff_secret="bff" * 11, public_base_url="http://test")
    )
    app.attach_oidc_login(oidc)
    with pytest.raises(ValueError, match="already called"):
        app.attach_oidc_login(oidc)


def test_flux_lit_attach_oidc_login_registers_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(GenericOIDCClient, "load_discovery_sync", lambda self: None)
    from fluxlit.auth.oidc import OIDCDiscoveryDocument

    oidc = GenericOIDCClient(
        GenericOIDCClientConfig(issuer="https://idp", client_id="c", client_secret="d")
    )
    oidc._doc = OIDCDiscoveryDocument.model_validate(  # noqa: SLF001
        {
            "issuer": "https://idp",
            "authorization_endpoint": "https://idp/a",
            "token_endpoint": "https://idp/t",
            "jwks_uri": "https://idp/j",
        }
    )
    app = FluxLit(
        settings=FluxlitSettings(oidc_bff_secret="bff" * 11, public_base_url="http://test")
    )
    app.attach_oidc_login(oidc)
    c = TestClient(app.api)
    assert c.get("/auth/login", follow_redirects=False).status_code == 302


def test_prepare_streamlit_api_client_returns_bearer_when_session_warmed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FLUXLIT_INTERNAL_API_BASE", raising=False)
    st = MagicMock()
    st.session_state = {"fluxlit_access_token": "pre"}
    st.query_params = {}
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(dict(request.headers))
        return httpx.Response(200)

    transport = httpx.MockTransport(handler)
    client = prepare_streamlit_api_client(
        st,
        base_url="http://127.0.0.1:8000/api",
    )
    client._client = httpx.Client(base_url=client._client.base_url, transport=transport)
    try:
        client.get("/ping")
    finally:
        client.close()
    assert captured.get("authorization") == "Bearer pre"


def test_prepare_streamlit_runs_exchange_then_bearer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLUXLIT_INTERNAL_API_BASE", raising=False)
    st = MagicMock()
    st.session_state = {}
    st.query_params = {"auth_code": "longenoughcode"}
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path.endswith("/auth/exchange"):
            return httpx.Response(200, json={"access_token": "newtok", "token_type": "bearer"})
        return httpx.Response(200)

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def client_with_transport(*args: object, **kwargs: object) -> httpx.Client:
        kwargs = {**kwargs, "transport": transport}
        return real_client(*args, **kwargs)

    with patch("fluxlit.client.httpx.Client", side_effect=client_with_transport):
        client = prepare_streamlit_api_client(st, base_url="http://127.0.0.1:8000/api")
    try:
        client.get("/x")
    finally:
        client.close()
    assert any(p.endswith("/auth/exchange") for p in paths)
    assert st.session_state.get("fluxlit_access_token") == "newtok"
