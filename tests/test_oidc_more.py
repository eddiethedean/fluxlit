from __future__ import annotations

from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from starlette.testclient import TestClient

from fluxlit.oidc import (
    GenericOIDCClient,
    GenericOIDCClientConfig,
    OIDCBFFConfig,
    OIDCDiscoveryDocument,
    _with_query,
    pkce_pair,
    register_oidc_bff_routes,
)


def _resp(
    status: int,
    method: str,
    url: str,
    *,
    json: object | None = None,
    text: str | None = None,
) -> httpx.Response:
    req = httpx.Request(method, url)
    if json is not None:
        return httpx.Response(status, request=req, json=json)
    if text is not None:
        return httpx.Response(status, request=req, text=text)
    return httpx.Response(status, request=req)


def test_pkce_pair_returns_verifier_and_challenge() -> None:
    v, c = pkce_pair()
    assert len(v) > 20
    assert isinstance(c, str) and len(c) > 20
    v2, c2 = pkce_pair()
    assert v != v2 and c != c2


def test_with_query_absolute_and_relative_base() -> None:
    u = _with_query(base="https://app.example", path="/dash", query={"a": "1"})
    assert u.startswith("https://app.example/dash")
    assert "a=1" in u
    rel = _with_query(base="noscheme", path="/p", query={"x": "y"})
    assert rel == "noscheme/p?x=y"


def test_generic_oidc_load_discovery_and_build_authorization_url() -> None:
    doc = {
        "issuer": "https://idp.example",
        "authorization_endpoint": "https://idp.example/oauth2/authorize",
        "token_endpoint": "https://idp.example/oauth2/token",
        "jwks_uri": "https://idp.example/jwks",
    }
    cfg = GenericOIDCClientConfig(
        issuer="https://idp.example",
        client_id="cid",
        client_secret="sec",
    )
    well_known = "https://idp.example/.well-known/openid-configuration"
    with patch("fluxlit.oidc.httpx.Client") as mock_cls:
        mock_http = MagicMock()
        mock_cls.return_value.__enter__.return_value = mock_http
        mock_http.get.return_value = _resp(200, "GET", well_known, json=doc)
        client = GenericOIDCClient(cfg)
        client.load_discovery_sync()

    assert client.issuer == "https://idp.example"
    auth_url = client.authorization_url(
        redirect_uri="https://app/cb",
        state="st",
        code_challenge="ch",
        scope="openid",
    )
    assert auth_url.startswith("https://idp.example/oauth2/authorize?")
    q = parse_qs(urlparse(auth_url).query)
    assert q["client_id"] == ["cid"]
    assert q["code_challenge"] == ["ch"]
    assert q["code_challenge_method"] == ["S256"]


def test_generic_oidc_discovery_http_error() -> None:
    well_known = "https://idp.example/.well-known/openid-configuration"
    cfg = GenericOIDCClientConfig(issuer="https://idp.example", client_id="i", client_secret="s")
    with patch("fluxlit.oidc.httpx.Client") as mock_cls:
        mock_http = MagicMock()
        mock_cls.return_value.__enter__.return_value = mock_http
        mock_http.get.return_value = _resp(404, "GET", well_known)
        client = GenericOIDCClient(cfg)
        with pytest.raises(httpx.HTTPStatusError):
            client.load_discovery_sync()


def test_generic_oidc_require_doc_before_discovery() -> None:
    c = GenericOIDCClient(
        GenericOIDCClientConfig(issuer="https://x", client_id="a", client_secret="b")
    )
    with pytest.raises(RuntimeError, match="load_discovery_sync"):
        c.authorization_url(redirect_uri="r", state="s", code_challenge="c")


def test_generic_oidc_exchange_non_object_json_raises() -> None:
    inner = {
        "issuer": "https://idp.example",
        "authorization_endpoint": "https://idp.example/a",
        "token_endpoint": "https://idp.example/t",
        "jwks_uri": "https://idp.example/j",
    }
    c = GenericOIDCClient(
        GenericOIDCClientConfig(issuer="https://idp.example", client_id="i", client_secret="s")
    )
    c._doc = OIDCDiscoveryDocument.model_validate(inner)  # noqa: SLF001

    with patch("fluxlit.oidc.httpx.Client") as mock_cls:
        mock_http = MagicMock()
        mock_cls.return_value.__enter__.return_value = mock_http
        tok = "https://idp.example/oauth2/token"
        mock_http.post.return_value = _resp(200, "POST", tok, json=[1, 2])
        with pytest.raises(ValueError, match="non-object"):
            c.exchange_code(code="x", code_verifier="v", redirect_uri="https://r/cb")


def test_generic_oidc_exchange_http_error_propagates() -> None:
    inner = {
        "issuer": "https://idp.example",
        "authorization_endpoint": "https://idp.example/a",
        "token_endpoint": "https://idp.example/t",
        "jwks_uri": "https://idp.example/j",
    }
    c = GenericOIDCClient(
        GenericOIDCClientConfig(issuer="https://idp.example", client_id="i", client_secret="s")
    )
    c._doc = OIDCDiscoveryDocument.model_validate(inner)  # noqa: SLF001

    with patch("fluxlit.oidc.httpx.Client") as mock_cls:
        mock_http = MagicMock()
        mock_cls.return_value.__enter__.return_value = mock_http
        tok = "https://idp.example/oauth2/token"
        mock_http.post.return_value = _resp(500, "POST", tok, text="err")
        with pytest.raises(httpx.HTTPStatusError):
            c.exchange_code(code="x", code_verifier="v", redirect_uri="https://r/cb")


class _MiniOidc:
    @property
    def issuer(self) -> str:
        return "x"

    def authorization_url(
        self,
        *,
        redirect_uri: str,
        state: str,
        code_challenge: str,
        scope: str | None = None,
    ) -> str:
        return f"https://x/authorize?state={state}&cc={code_challenge}"

    def exchange_code(self, **_: object) -> dict[str, str]:
        return {}


def test_bff_callback_missing_code_or_state() -> None:
    app = FastAPI()
    register_oidc_bff_routes(
        app,
        OIDCBFFConfig(oidc=_MiniOidc(), first_party_secret="bff-first-party-secret-32bytes-x"),
    )
    c = TestClient(app)
    assert c.get("/auth/callback", params={"code": "", "state": "s"}).status_code == 400
    assert c.get("/auth/callback", params={"code": "c", "state": ""}).status_code == 400


def test_bff_callback_invalid_state() -> None:
    app = FastAPI()
    register_oidc_bff_routes(
        app,
        OIDCBFFConfig(oidc=_MiniOidc(), first_party_secret="bff-first-party-secret-32bytes-x"),
    )
    c = TestClient(app)
    assert c.get("/auth/callback", params={"code": "c", "state": "unknown"}).status_code == 400


def test_bff_callback_missing_id_token() -> None:
    class _NoIdToken(_MiniOidc):
        def exchange_code(self, **_: object) -> dict[str, str]:
            return {"access_token": "only"}

    app = FastAPI()
    register_oidc_bff_routes(
        app,
        OIDCBFFConfig(oidc=_NoIdToken(), first_party_secret="bff-first-party-secret-32bytes-x"),
    )
    c = TestClient(app)
    r1 = c.get("/auth/login", follow_redirects=False)
    state = parse_qs(urlparse(r1.headers["location"]).query)["state"][0]
    r2 = c.get("/auth/callback", params={"code": "c", "state": state}, follow_redirects=False)
    assert r2.status_code == 502


def test_bff_callback_invalid_id_token_jwt() -> None:
    class _BadIdToken(_MiniOidc):
        def exchange_code(self, **_: object) -> dict[str, str]:
            return {"id_token": "not-a-jwt", "access_token": "a"}

    app = FastAPI()
    register_oidc_bff_routes(
        app,
        OIDCBFFConfig(oidc=_BadIdToken(), first_party_secret="bff-first-party-secret-32bytes-x"),
    )
    c = TestClient(app)
    r1 = c.get("/auth/login", follow_redirects=False)
    state = parse_qs(urlparse(r1.headers["location"]).query)["state"][0]
    r2 = c.get("/auth/callback", params={"code": "c", "state": state}, follow_redirects=False)
    assert r2.status_code == 502


def test_bff_callback_id_token_missing_sub() -> None:
    import base64

    h = base64.urlsafe_b64encode(b'{"alg":"none"}').decode().rstrip("=")
    p = base64.urlsafe_b64encode(b'{"no_sub":true}').decode().rstrip("=")
    bad_tok = f"{h}.{p}.x"

    class _NoSub(_MiniOidc):
        def exchange_code(self, **_: object) -> dict[str, str]:
            return {"id_token": bad_tok, "access_token": "a"}

    app = FastAPI()
    register_oidc_bff_routes(
        app,
        OIDCBFFConfig(oidc=_NoSub(), first_party_secret="bff-first-party-secret-32bytes-x"),
    )
    c = TestClient(app)
    r1 = c.get("/auth/login", follow_redirects=False)
    state = parse_qs(urlparse(r1.headers["location"]).query)["state"][0]
    r2 = c.get("/auth/callback", params={"code": "c", "state": state}, follow_redirects=False)
    assert r2.status_code == 502


def test_exchange_validates_min_code_length() -> None:
    app = FastAPI()
    register_oidc_bff_routes(
        app,
        OIDCBFFConfig(oidc=_MiniOidc(), first_party_secret="bff-first-party-secret-32bytes-x"),
    )
    assert TestClient(app).post("/auth/exchange", json={"code": "short"}).status_code == 422


def test_bff_callback_generic_oidc_uses_jwks_verify(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    def fake_verify(
        *,
        id_token: str,
        issuer: str,
        jwks_uri: str,
        audience: str,
        leeway: int = 0,
    ) -> str:
        captured["id_token"] = id_token
        captured["issuer"] = issuer
        captured["jwks_uri"] = jwks_uri
        captured["audience"] = audience
        captured["leeway"] = str(leeway)
        return "jwks-verified-sub"

    monkeypatch.setattr("fluxlit.oidc._verify_id_token_jwks", fake_verify)

    inner = {
        "issuer": "https://idp.example",
        "authorization_endpoint": "https://idp.example/a",
        "token_endpoint": "https://idp.example/t",
        "jwks_uri": "https://idp.example/jwks",
    }
    cfg = GenericOIDCClientConfig(
        issuer="https://idp.example",
        client_id="my-client",
        client_secret="sec",
    )
    oidc = GenericOIDCClient(cfg)
    oidc._doc = OIDCDiscoveryDocument.model_validate(inner)  # noqa: SLF001

    def exchange_code(self: object, **_: object) -> dict[str, str]:
        return {"id_token": "header.payload.sig", "access_token": "at"}

    monkeypatch.setattr(GenericOIDCClient, "exchange_code", exchange_code)

    app = FastAPI()
    register_oidc_bff_routes(
        app,
        OIDCBFFConfig(
            oidc=oidc,
            first_party_secret="bff-first-party-secret-32bytes-x",
            id_token_leeway_seconds=5,
        ),
    )
    c = TestClient(app)
    r1 = c.get("/auth/login", follow_redirects=False)
    assert r1.status_code == 302
    state = parse_qs(urlparse(r1.headers["location"]).query)["state"][0]
    r2 = c.get(
        "/auth/callback", params={"code": "auth-code-here", "state": state}, follow_redirects=False
    )
    assert r2.status_code == 302
    assert captured["id_token"] == "header.payload.sig"
    assert captured["issuer"] == "https://idp.example"
    assert captured["jwks_uri"] == "https://idp.example/jwks"
    assert captured["audience"] == "my-client"
    assert captured["leeway"] == "5"


def test_verify_id_token_jwks_invalid_token_raises_502() -> None:
    jwt_lib = pytest.importorskip("jwt")
    from fluxlit.oidc import _verify_id_token_jwks

    jwks = MagicMock()
    sk = MagicMock()
    sk.key = object()
    jwks.get_signing_key_from_jwt.return_value = sk
    with patch.object(jwt_lib, "PyJWKClient", return_value=jwks):
        with patch.object(jwt_lib, "decode", side_effect=jwt_lib.InvalidTokenError("bad")):
            with pytest.raises(HTTPException) as excinfo:
                _verify_id_token_jwks(
                    id_token="a.b.c",
                    issuer="https://iss",
                    jwks_uri="https://jwks",
                    audience="aud",
                )
    assert excinfo.value.status_code == 502
