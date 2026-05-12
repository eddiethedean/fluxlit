from __future__ import annotations

import base64
import json
from urllib.parse import parse_qs, urlparse

from fastapi import FastAPI
from starlette.testclient import TestClient

from fluxlit.auth.oidc import OIDCBFFConfig, register_oidc_bff_routes


def _unsigned_id_token(sub: str) -> str:
    h = base64.urlsafe_b64encode(b'{"alg":"none"}').decode().rstrip("=")
    p = base64.urlsafe_b64encode(json.dumps({"sub": sub}).encode()).decode().rstrip("=")
    return f"{h}.{p}."


class _StubOIDC:
    @property
    def issuer(self) -> str:
        return "https://stub.example"

    def authorization_url(
        self,
        *,
        redirect_uri: str,
        state: str,
        code_challenge: str,
        scope: str | None = None,
    ) -> str:
        q = f"redirect_uri={redirect_uri}&state={state}&cc={code_challenge}"
        return f"https://stub.example/authorize?{q}"

    def exchange_code(
        self,
        *,
        code: str,
        code_verifier: str,
        redirect_uri: str,
    ) -> dict[str, str]:
        return {"id_token": _unsigned_id_token("user-42"), "access_token": "opaque"}


def test_oidc_bff_login_callback_exchange() -> None:
    app = FastAPI()
    cfg = OIDCBFFConfig(
        oidc=_StubOIDC(),
        first_party_secret="bff-first-party-secret-32bytes-x",
        token_issuer="bff",
        token_audience="app",
        access_token_ttl_seconds=600,
        public_base_url="http://testserver",
        allow_unverified_id_token_for_custom_oidc=True,
    )
    register_oidc_bff_routes(app, cfg)
    client = TestClient(app)

    r1 = client.get("/auth/login", follow_redirects=False)
    assert r1.status_code == 302
    loc1 = r1.headers["location"]
    state = parse_qs(urlparse(loc1).query)["state"][0]

    r2 = client.get(
        "/auth/callback",
        params={"code": "from-idp", "state": state},
        follow_redirects=False,
    )
    assert r2.status_code == 302
    loc2 = r2.headers["location"]
    assert "auth_code=" in loc2
    auth_code = parse_qs(urlparse(loc2).query)["auth_code"][0]

    r3 = client.post("/auth/exchange", json={"code": auth_code})
    assert r3.status_code == 200
    body = r3.json()
    assert body.get("token_type") == "bearer"
    assert isinstance(body.get("access_token"), str) and body["access_token"]


def test_oidc_login_redirect_uri_uses_public_base_and_callback_path() -> None:
    """IdP redirect_uri must match browser-visible origin + API callback (subpath-safe)."""
    app = FastAPI()
    cfg = OIDCBFFConfig(
        oidc=_StubOIDC(),
        first_party_secret="bff-first-party-secret-32bytes-x",
        public_base_url="https://customer.example/connect",
        callback_path="/api/auth/callback",
        allow_unverified_id_token_for_custom_oidc=True,
    )
    register_oidc_bff_routes(app, cfg)
    client = TestClient(app)
    r = client.get("/auth/login", follow_redirects=False)
    assert r.status_code == 302
    loc = r.headers["location"]
    q = parse_qs(urlparse(loc).query)
    redirect_uri = q["redirect_uri"][0]
    assert redirect_uri == "https://customer.example/connect/api/auth/callback"


def test_oidc_bff_exchange_rejects_reuse() -> None:
    app = FastAPI()
    cfg = OIDCBFFConfig(
        oidc=_StubOIDC(),
        first_party_secret="bff-first-party-secret-32bytes-x",
        public_base_url="http://testserver",
        allow_unverified_id_token_for_custom_oidc=True,
    )
    register_oidc_bff_routes(app, cfg)
    client = TestClient(app)
    client.get("/auth/login", follow_redirects=False)
    # state unknown — use full flow
    r1 = client.get("/auth/login", follow_redirects=False)
    state = parse_qs(urlparse(r1.headers["location"]).query)["state"][0]
    r2 = client.get(
        "/auth/callback",
        params={"code": "c", "state": state},
        follow_redirects=False,
    )
    auth_code = parse_qs(urlparse(r2.headers["location"]).query)["auth_code"][0]
    assert client.post("/auth/exchange", json={"code": auth_code}).status_code == 200
    assert client.post("/auth/exchange", json={"code": auth_code}).status_code == 401
