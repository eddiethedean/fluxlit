from __future__ import annotations

from fastapi import Depends, FastAPI
from starlette.testclient import TestClient

from fluxlit.auth import TrustedProxyUser, TrustedProxyUserConfig, proxy_user_header


def test_proxy_user_header_reads_configured_header() -> None:
    app = FastAPI()

    @app.get("/me")
    def me(user: str | None = Depends(proxy_user_header("X-Custom-User"))) -> dict[str, str | None]:
        return {"user": user}

    client = TestClient(app)
    r = client.get("/me", headers={"X-Custom-User": "alice"})
    assert r.status_code == 200
    assert r.json() == {"user": "alice"}

    r2 = client.get("/me")
    assert r2.json() == {"user": None}


def test_trusted_proxy_user_requires_https_when_configured() -> None:
    app = FastAPI()
    _https = TrustedProxyUser(TrustedProxyUserConfig(require_https=True))

    @app.get("/me")
    def me(user: str = Depends(_https)) -> dict[str, str]:  # noqa: B008
        return {"user": user}

    client = TestClient(app)
    r = client.get("/me", headers={"X-Remote-User": "alice"})
    assert r.status_code == 403

    r2 = client.get(
        "/me",
        headers={"X-Remote-User": "alice", "X-Forwarded-Proto": "https"},
    )
    assert r2.status_code == 200
    assert r2.json() == {"user": "alice"}


def test_trusted_proxy_user_trusted_client_hosts() -> None:
    app = FastAPI()
    dep = TrustedProxyUser(TrustedProxyUserConfig(trusted_client_hosts=frozenset({"testclient"})))

    @app.get("/me")
    def me(user: str = Depends(dep)) -> dict[str, str]:  # noqa: B008
        return {"user": user}

    client = TestClient(app)
    r = client.get("/me", headers={"X-Remote-User": "bob"})
    assert r.status_code == 200


def test_trusted_proxy_user_allows_empty_header_when_optional() -> None:
    app = FastAPI()
    dep = TrustedProxyUser(
        TrustedProxyUserConfig(
            header_name="X-User",
            require_non_empty_user=False,
        )
    )

    @app.get("/me")
    def me(user: str = Depends(dep)) -> dict[str, str]:  # noqa: B008
        return {"user": user}

    client = TestClient(app)
    r = client.get("/me")
    assert r.status_code == 200
    assert r.json() == {"user": ""}


def test_trusted_proxy_user_rejects_untrusted_client_host() -> None:
    app = FastAPI()
    dep = TrustedProxyUser(TrustedProxyUserConfig(trusted_client_hosts=frozenset({"127.0.0.1"})))

    @app.get("/me")
    def me(user: str = Depends(dep)) -> dict[str, str]:  # noqa: B008
        return {"user": user}

    client = TestClient(app)
    assert client.get("/me", headers={"X-Remote-User": "eve"}).status_code == 403


def test_trusted_proxy_user_requires_non_empty_header_by_default() -> None:
    app = FastAPI()
    dep = TrustedProxyUser(TrustedProxyUserConfig())

    @app.get("/me")
    def me(user: str = Depends(dep)) -> dict[str, str]:  # noqa: B008
        return {"user": user}

    client = TestClient(app)
    assert client.get("/me").status_code == 401
    assert client.get("/me", headers={"X-Remote-User": "   "}).status_code == 401
