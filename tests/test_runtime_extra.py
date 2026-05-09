from __future__ import annotations

import errno
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from fluxlit.runtime import _wait_for_tcp, create_gateway_app


def test_wait_for_tcp_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise OSError(errno.ECONNREFUSED, "refused")

    monkeypatch.setattr("fluxlit.runtime.socket.create_connection", refuse)
    clock = {"t": 0.0}

    def monotonic() -> float:
        cur = clock["t"]
        clock["t"] += 35.0
        return cur

    monkeypatch.setattr("fluxlit.runtime.time.monotonic", monotonic)
    monkeypatch.setattr("fluxlit.runtime.time.sleep", lambda _s: None)

    with pytest.raises(TimeoutError, match="Timed out waiting"):
        _wait_for_tcp("127.0.0.1", 59999, timeout_s=30.0)


def test_create_gateway_app_reads_env_and_proxies_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "cg_app.py").write_text(
        "from fluxlit import FluxLit\napp = FluxLit(title='CG')\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv("FLUXLIT_APP", "cg_app:app")
    monkeypatch.setenv("FLUXLIT_STREAMLIT_UPSTREAM", "http://127.0.0.1:9")
    monkeypatch.setenv("FLUXLIT_API_PREFIX", "/api")

    asgi = create_gateway_app()
    client = TestClient(asgi)
    assert client.get("/api/healthz").status_code == 200
    assert client.get("/nope").status_code == 502
