from __future__ import annotations

from fastapi import Depends, FastAPI
from starlette.testclient import TestClient

from fluxlit.auth import proxy_user_header


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
