from __future__ import annotations

import contextlib
import errno
import subprocess
import sys
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from fluxlit.runtime import (
    _wait_for_tcp,
    create_gateway_app,
    default_pidfile_path,
    shutdown_unified_process,
)


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


def test_create_gateway_app_requires_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLUXLIT_APP", raising=False)
    monkeypatch.delenv("FLUXLIT_STREAMLIT_UPSTREAM", raising=False)
    with pytest.raises(RuntimeError, match="FLUXLIT_APP"):
        create_gateway_app()


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


def test_default_pidfile_path_cwd_and_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert default_pidfile_path() == tmp_path / ".fluxlit-dev.pid"
    monkeypatch.setenv("FLUXLIT_PIDFILE", str(tmp_path / "via_env.pid"))
    assert default_pidfile_path() == tmp_path / "via_env.pid"
    monkeypatch.delenv("FLUXLIT_PIDFILE", raising=False)
    assert default_pidfile_path(tmp_path / "custom.pid") == tmp_path / "custom.pid"


def test_shutdown_unified_process_missing_file(tmp_path: Path) -> None:
    code, msg = shutdown_unified_process(tmp_path / "missing.pid")
    assert code == 2
    assert "No pid file" in msg


def test_shutdown_unified_process_stale_pid(tmp_path: Path) -> None:
    pid_path = tmp_path / ".fluxlit-dev.pid"
    pid_path.write_text("999999999\n", encoding="ascii")
    code, msg = shutdown_unified_process(pid_path)
    assert code == 0
    assert "stale" in msg.lower() or "not running" in msg.lower()
    assert not pid_path.exists()


def test_shutdown_unified_process_invalid_contents(tmp_path: Path) -> None:
    pid_path = tmp_path / "bad.pid"
    pid_path.write_text("not-an-int\n", encoding="ascii")
    code, msg = shutdown_unified_process(pid_path)
    assert code == 0
    assert "invalid" in msg.lower() or "removed" in msg.lower()
    assert not pid_path.exists()


def test_shutdown_unified_process_terminates_child(tmp_path: Path) -> None:
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    pid_path = tmp_path / "child.pid"
    pid_path.write_text(f"{proc.pid}\n", encoding="ascii")
    try:
        code, _msg = shutdown_unified_process(pid_path, wait_s=5.0)
        assert code == 0
        proc.wait(timeout=10)
        assert proc.returncode is not None
    finally:
        with contextlib.suppress(Exception):
            proc.kill()
            proc.wait(timeout=2)
