"""RS256 validation via a real JWKS document served over HTTP."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, FastAPI
from jwt.algorithms import RSAAlgorithm
from starlette.testclient import TestClient

from fluxlit.auth.jwt import JWTAuthConfig, JWTBearer, StandardClaims


@pytest.fixture
def rsa_jwks_server() -> Any:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = private_key.public_key()
    jwk_dict = dict(RSAAlgorithm.to_jwk(pub, as_dict=True))
    jwk_dict.update({"kid": "unit-kid", "use": "sig", "alg": "RS256"})
    body = json.dumps({"keys": [jwk_dict]}).encode()

    class _JwksHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/.well-known/jwks.json":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_error(404)

        def log_message(self, *_args: Any) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), _JwksHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    try:
        yield f"http://127.0.0.1:{port}", pem
    finally:
        server.shutdown()
        thread.join(timeout=10)


def _rs256_token(
    *,
    private_pem: bytes,
    subject: str,
    audience: str = "my-api",
    issuer: str = "https://issuer.example",
) -> str:
    now = datetime.now(timezone.utc)
    exp = int((now + timedelta(minutes=5)).timestamp())
    payload = {
        "sub": subject,
        "iss": issuer,
        "aud": audience,
        "exp": exp,
        "iat": int(now.timestamp()),
    }
    return jwt.encode(
        payload,
        private_pem,
        algorithm="RS256",
        headers={"kid": "unit-kid"},
    )


def test_jwt_bearer_accepts_rs256_from_live_jwks(rsa_jwks_server: tuple[str, bytes]) -> None:
    base, pem = rsa_jwks_server
    bearer = JWTBearer(
        JWTAuthConfig(
            issuer="https://issuer.example",
            audience="my-api",
            algorithms=["RS256"],
            jwks_url=f"{base}/.well-known/jwks.json",
        )
    )
    app = FastAPI()

    @app.get("/who")
    async def who(c: StandardClaims = Depends(bearer)):  # noqa: B008
        return {"sub": c.sub}

    token = _rs256_token(private_pem=pem, subject="jwks-alice")
    client = TestClient(app)
    r = client.get("/who", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == {"sub": "jwks-alice"}


def test_jwt_bearer_rs256_rejects_wrong_audience(rsa_jwks_server: tuple[str, bytes]) -> None:
    base, pem = rsa_jwks_server
    bearer = JWTBearer(
        JWTAuthConfig(
            issuer="https://issuer.example",
            audience="expected-aud",
            algorithms=["RS256"],
            jwks_url=f"{base}/.well-known/jwks.json",
        )
    )
    app = FastAPI()

    @app.get("/x")
    async def x(_c: StandardClaims = Depends(bearer)):  # noqa: B008
        return {"ok": True}

    token = _rs256_token(private_pem=pem, subject="u", audience="wrong-aud")
    client = TestClient(app)
    assert client.get("/x", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_jwt_bearer_rs256_leeway_skew(rsa_jwks_server: tuple[str, bytes]) -> None:
    base, pem = rsa_jwks_server
    bearer = JWTBearer(
        JWTAuthConfig(
            issuer="https://issuer.example",
            audience="my-api",
            algorithms=["RS256"],
            jwks_url=f"{base}/.well-known/jwks.json",
            leeway_seconds=120,
        )
    )
    app = FastAPI()

    @app.get("/who")
    async def who(c: StandardClaims = Depends(bearer)):  # noqa: B008
        return {"sub": c.sub}

    now = datetime.now(timezone.utc)
    exp = int((now - timedelta(seconds=45)).timestamp())
    token = jwt.encode(
        {
            "sub": "skew",
            "iss": "https://issuer.example",
            "aud": "my-api",
            "exp": exp,
            "iat": int((now - timedelta(minutes=1)).timestamp()),
        },
        pem,
        algorithm="RS256",
        headers={"kid": "unit-kid"},
    )
    client = TestClient(app)
    r = client.get("/who", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
