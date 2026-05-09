from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from starlette.testclient import TestClient

from fluxlit.jwt_auth import (
    JWTAuthConfig,
    JWTBearer,
    RequireRoles,
    RequireScopes,
    StandardClaims,
    issue_hs256_access_token,
)

_HS_SECRET = "unit-test-hmac-secret-32bytes-xx"


@pytest.fixture
def hs256_bearer() -> JWTBearer:
    return JWTBearer(
        JWTAuthConfig(
            issuer="https://issuer.example",
            audience="my-api",
            algorithms=["HS256"],
            hs256_secret=_HS_SECRET,
        )
    )


def test_jwt_bearer_accepts_valid_hs256(hs256_bearer: JWTBearer) -> None:
    app = FastAPI()
    bearer = hs256_bearer

    @app.get("/who")
    async def who(c: StandardClaims = Depends(bearer)):  # noqa: B008
        return {"sub": c.sub}

    token = issue_hs256_access_token(
        subject="alice",
        issuer="https://issuer.example",
        audience="my-api",
        secret=_HS_SECRET,
        ttl_seconds=300,
    )
    client = TestClient(app)
    r = client.get("/who", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == {"sub": "alice"}


def test_jwt_bearer_rejects_missing_header(hs256_bearer: JWTBearer) -> None:
    app = FastAPI()
    bearer = hs256_bearer

    @app.get("/who")
    async def who(_c: StandardClaims = Depends(bearer)):  # noqa: B008
        return {"ok": True}

    client = TestClient(app)
    r = client.get("/who")
    assert r.status_code == 401


def test_require_scopes_enforces_scope_claim(hs256_bearer: JWTBearer) -> None:
    app = FastAPI()
    need = RequireScopes(hs256_bearer, "read", "write")
    dep = need

    @app.get("/data")
    async def data(_c: StandardClaims = Depends(dep)):  # noqa: B008
        return {"ok": True}

    token = issue_hs256_access_token(
        subject="bob",
        issuer="https://issuer.example",
        audience="my-api",
        secret=_HS_SECRET,
        ttl_seconds=300,
        extra_claims={"scope": "read write"},
    )
    client = TestClient(app)
    assert client.get("/data", headers={"Authorization": f"Bearer {token}"}).status_code == 200

    bad = issue_hs256_access_token(
        subject="bob",
        issuer="https://issuer.example",
        audience="my-api",
        secret=_HS_SECRET,
        ttl_seconds=300,
        extra_claims={"scope": "read"},
    )
    r2 = client.get("/data", headers={"Authorization": f"Bearer {bad}"})
    assert r2.status_code == 403


def test_require_roles_enforces_roles_claim(hs256_bearer: JWTBearer) -> None:
    app = FastAPI()
    need = RequireRoles(hs256_bearer, "admin", roles_claim="roles")
    dep = need

    @app.get("/admin")
    async def admin(_c: StandardClaims = Depends(dep)):  # noqa: B008
        return {"ok": True}

    token = issue_hs256_access_token(
        subject="carol",
        issuer="https://issuer.example",
        audience="my-api",
        secret=_HS_SECRET,
        ttl_seconds=300,
        extra_claims={"roles": ["admin", "user"]},
    )
    client = TestClient(app)
    assert client.get("/admin", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_issue_hs256_requires_auth_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    import fluxlit.jwt_auth as ja

    def boom() -> None:
        raise RuntimeError("no jwt")

    monkeypatch.setattr(ja, "_require_pyjwt", boom)
    with pytest.raises(RuntimeError, match="no jwt"):
        issue_hs256_access_token(
            subject="x",
            issuer="i",
            audience="a",
            secret="s",
            ttl_seconds=1,
        )
