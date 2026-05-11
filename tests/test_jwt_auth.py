from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from starlette.testclient import TestClient

from fluxlit.auth.jwt import (
    JWTAuthConfig,
    JWTBearer,
    RequireRoles,
    RequireScopes,
    StandardClaims,
    _claims_roles,
    _claims_scopes,
    issue_hs256_access_token,
)
from fluxlit.config import FluxlitSettings

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


@pytest.mark.asyncio
async def test_jwt_bearer_hs256_decode_uses_anyio_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    """JWKS/HS256 sync decode must run via anyio.to_thread (non-blocking contract)."""
    bearer = JWTBearer(
        JWTAuthConfig(
            issuer="https://issuer.example",
            audience="my-api",
            algorithms=["HS256"],
            hs256_secret=_HS_SECRET,
        )
    )
    token = issue_hs256_access_token(
        subject="thread-check",
        issuer="https://issuer.example",
        audience="my-api",
        secret=_HS_SECRET,
        ttl_seconds=300,
    )
    ran_in_thread: list[bool] = []

    async def fake_run_sync(func: object, *args: object) -> object:
        ran_in_thread.append(True)
        if not callable(func):
            raise TypeError("expected callable")
        return func(*args)

    monkeypatch.setattr("fluxlit.auth.jwt.anyio.to_thread.run_sync", fake_run_sync)
    from starlette.requests import Request

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"authorization", f"Bearer {token}".encode())],
    }
    request = Request(scope)
    claims = await bearer(request)
    assert ran_in_thread == [True]
    assert claims.sub == "thread-check"


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


def test_jwt_bearer_from_settings_accepts_jwks_url(monkeypatch: pytest.MonkeyPatch) -> None:
    import fluxlit.auth.jwt as jwt_module

    class FakeJwksClient:
        def __init__(self, url: str) -> None:
            self.url = url

    real = jwt_module._require_pyjwt()
    monkeypatch.setattr(
        jwt_module,
        "_require_pyjwt",
        lambda: type("JwtMod", (), {**real.__dict__, "PyJWKClient": FakeJwksClient}),
    )
    bearer = JWTBearer.from_fluxlit_settings(
        FluxlitSettings(
            jwt_issuer="https://iss",
            jwt_audience="aud",
            jwt_jwks_url="https://issuer.example/jwks",
        )
    )
    assert isinstance(bearer, JWTBearer)


def test_jwt_bearer_from_settings_requires_secret_or_jwks() -> None:
    with pytest.raises(ValueError, match="HS256_SECRET or FLUXLIT_JWT_JWKS_URL"):
        JWTBearer.from_fluxlit_settings(
            FluxlitSettings(jwt_issuer="https://iss", jwt_audience="aud")
        )


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


def test_claim_scope_and_role_helpers_handle_missing_strings_lists_and_other_values() -> None:
    assert _claims_scopes(StandardClaims(sub="s", iss="i", aud="a"), "scope") == set()
    assert _claims_scopes(
        StandardClaims.model_construct(sub="s", iss="i", aud="a", scope=["read", 2]), "scope"
    ) == {"read", "2"}
    assert (
        _claims_scopes(
            StandardClaims.model_construct(sub="s", iss="i", aud="a", scope={"bad": "shape"}),
            "scope",
        )
        == set()
    )
    assert _claims_roles(StandardClaims(sub="s", iss="i", aud="a"), "roles") == set()
    assert _claims_roles(
        StandardClaims.model_construct(sub="s", iss="i", aud="a", roles="admin"), "roles"
    ) == {"admin"}
    assert (
        _claims_roles(
            StandardClaims.model_construct(sub="s", iss="i", aud="a", roles={"bad": "shape"}),
            "roles",
        )
        == set()
    )


def test_issue_hs256_requires_auth_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    import fluxlit.auth.jwt as ja

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


def test_jwt_auth_config_hs256_requires_hs256_alg() -> None:
    with pytest.raises(ValueError, match="HS256"):
        JWTBearer(
            JWTAuthConfig(
                issuer="i",
                audience="a",
                algorithms=["RS256"],
                hs256_secret="x" * 32,
            )
        )


def test_jwt_auth_config_requires_secret_or_jwks() -> None:
    with pytest.raises(ValueError, match="Either hs256_secret"):
        JWTBearer(JWTAuthConfig(issuer="i", audience="a", algorithms=["RS256"], jwks_url=None))


def test_jwt_bearer_rejects_empty_bearer_value(hs256_bearer: JWTBearer) -> None:
    app = FastAPI()

    @app.get("/x")
    async def x(_c: StandardClaims = Depends(hs256_bearer)):  # noqa: B008
        return {"ok": True}

    r = TestClient(app).get("/x", headers={"Authorization": "Bearer "})
    assert r.status_code == 401
    assert r.json()["detail"] == "Empty bearer token"


def test_jwt_bearer_accepts_lowercase_bearer_prefix(hs256_bearer: JWTBearer) -> None:
    app = FastAPI()
    bearer = hs256_bearer

    @app.get("/x")
    async def x(c: StandardClaims = Depends(bearer)):  # noqa: B008
        return {"sub": c.sub}

    token = issue_hs256_access_token(
        subject="d",
        issuer="https://issuer.example",
        audience="my-api",
        secret=_HS_SECRET,
        ttl_seconds=60,
    )
    r = TestClient(app).get("/x", headers={"authorization": f"bearer {token}"})
    assert r.status_code == 200


def test_jwt_bearer_rejects_expired_token(hs256_bearer: JWTBearer) -> None:
    app = FastAPI()
    bearer = hs256_bearer

    @app.get("/x")
    async def x(_c: StandardClaims = Depends(bearer)):  # noqa: B008
        return {"ok": True}

    token = issue_hs256_access_token(
        subject="e",
        issuer="https://issuer.example",
        audience="my-api",
        secret=_HS_SECRET,
        ttl_seconds=-3600,
    )
    r = TestClient(app).get("/x", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Token expired"


def test_jwt_bearer_rejects_bad_signature(hs256_bearer: JWTBearer) -> None:
    app = FastAPI()
    bearer = hs256_bearer

    @app.get("/x")
    async def x(_c: StandardClaims = Depends(bearer)):  # noqa: B008
        return {"ok": True}

    token = issue_hs256_access_token(
        subject="f",
        issuer="https://issuer.example",
        audience="my-api",
        secret="wrong-secret-not-the-same-as-bearer-config-",
        ttl_seconds=300,
    )
    r = TestClient(app).get("/x", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid token"


def test_require_roles_forbidden_when_missing_role(hs256_bearer: JWTBearer) -> None:
    app = FastAPI()
    dep = RequireRoles(hs256_bearer, "admin", roles_claim="roles")

    @app.get("/x")
    async def x(_c: StandardClaims = Depends(dep)):  # noqa: B008
        return {"ok": True}

    token = issue_hs256_access_token(
        subject="g",
        issuer="https://issuer.example",
        audience="my-api",
        secret=_HS_SECRET,
        ttl_seconds=300,
        extra_claims={"roles": ["viewer"]},
    )
    r = TestClient(app).get("/x", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_require_scopes_accepts_list_claim_under_custom_name(hs256_bearer: JWTBearer) -> None:
    app = FastAPI()
    dep = RequireScopes(hs256_bearer, "api.read", scope_claim="scp")

    @app.get("/x")
    async def x(_c: StandardClaims = Depends(dep)):  # noqa: B008
        return {"ok": True}

    token = issue_hs256_access_token(
        subject="h",
        issuer="https://issuer.example",
        audience="my-api",
        secret=_HS_SECRET,
        ttl_seconds=300,
        extra_claims={"scp": ["api.read", "api.write"]},
    )
    r = TestClient(app).get("/x", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


def test_jwt_bearer_rs256_with_mocked_jwks_client(monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import datetime, timezone
    from unittest.mock import MagicMock

    import jwt as pyjwt
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    now = datetime.now(timezone.utc)
    exp = int(now.timestamp()) + 3600
    token = pyjwt.encode(
        {
            "sub": "rsa-user",
            "iss": "https://rsa.issuer",
            "aud": "rsa-aud",
            "iat": int(now.timestamp()),
            "exp": exp,
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "k1"},
    )

    mock_client = MagicMock()
    mock_client.get_signing_key_from_jwt.return_value = MagicMock(key=public_key)
    monkeypatch.setattr(pyjwt, "PyJWKClient", MagicMock(return_value=mock_client))

    bearer = JWTBearer(
        JWTAuthConfig(
            issuer="https://rsa.issuer",
            audience="rsa-aud",
            algorithms=["RS256"],
            jwks_url="https://issuer.example/jwks.json",
        )
    )

    app = FastAPI()

    @app.get("/x")
    async def x(c: StandardClaims = Depends(bearer)):  # noqa: B008
        return {"sub": c.sub}

    r = TestClient(app).get("/x", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["sub"] == "rsa-user"


def test_require_pyjwt_import_error_message(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    import fluxlit.auth.jwt as ja

    real_import = builtins.__import__

    def fake_import(
        name: str,
        globals_arg: dict | None = None,
        locals_arg: dict | None = None,
        fromlist: tuple = (),
        level: int = 0,
    ):
        if name == "jwt":
            raise ImportError("No module named 'jwt'")
        return real_import(name, globals_arg, locals_arg, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(RuntimeError, match="fluxlit\\[auth\\]"):
        ja._require_pyjwt()
