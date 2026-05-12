from __future__ import annotations

import asyncio
import contextlib
import errno
import os
import signal
import subprocess
import sys
import types
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from fluxlit import FluxLit
from fluxlit.runtime import (
    _wait_for_tcp,
    create_gateway_app,
    default_pidfile_path,
    resolve_import_target_for_unified,
    run_unified,
    shutdown_unified_process,
)
from fluxlit.runtime.process_control import (
    _pid_is_zombie_unix,
    _pid_running,
    _remove_pidfile,
    _windows_taskkill_tree,
    _write_pidfile,
)
from fluxlit.runtime.streamlit_proc import _terminate_process
from fluxlit.runtime.wait_tcp import _invoke_wait_for_tcp


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


def test_wait_for_tcp_returns_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    class Conn:
        def __enter__(self) -> Conn:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    calls: list[tuple[str, int]] = []

    def connect(addr: tuple[str, int], timeout: float) -> Conn:
        calls.append(addr)
        return Conn()

    monkeypatch.setattr("fluxlit.runtime.wait_tcp.socket.create_connection", connect)
    _wait_for_tcp("127.0.0.1", 1234, timeout_s=1.0)
    assert calls == [("127.0.0.1", 1234)]


def test_wait_for_tcp_retries_after_oserror(monkeypatch: pytest.MonkeyPatch) -> None:
    class Conn:
        def __enter__(self) -> Conn:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    attempts = {"n": 0}

    def connect(addr: tuple[str, int], timeout: float) -> Conn:
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise OSError("not yet")
        return Conn()

    monkeypatch.setattr("fluxlit.runtime.wait_tcp.socket.create_connection", connect)
    monkeypatch.setattr("fluxlit.runtime.wait_tcp.time.sleep", lambda s: None)
    _wait_for_tcp("127.0.0.1", 1234, timeout_s=1.0)
    assert attempts["n"] == 2


def test_invoke_wait_for_tcp_uses_runtime_package_monkeypatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: dict[str, object] = {}

    def fake_wait(host: str, port: int, timeout_s: float) -> None:
        called.update({"host": host, "port": port, "timeout_s": timeout_s})

    monkeypatch.setattr("fluxlit.runtime._wait_for_tcp", fake_wait)
    _invoke_wait_for_tcp("h", 9, 1.5)
    assert called == {"host": "h", "port": 9, "timeout_s": 1.5}


def test_create_gateway_app_requires_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLUXLIT_APP", raising=False)
    monkeypatch.delenv("FLUXLIT_STREAMLIT_UPSTREAM", raising=False)
    monkeypatch.delenv("FLUXLIT_STREAMLIT_UPSTREAM_FILE", raising=False)
    with pytest.raises(RuntimeError, match="FLUXLIT_APP"):
        create_gateway_app()


def test_create_unified_app_requires_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from fluxlit.runtime import create_unified_app

    monkeypatch.delenv("FLUXLIT_APP", raising=False)
    with pytest.raises(RuntimeError, match="FLUXLIT_APP"):
        create_unified_app()


@pytest.mark.asyncio
async def test_lifespan_bridge_windows_creationflags_and_unknown_lifespan_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fluxlit import FluxLit
    from fluxlit.runtime.lifespan_bridge import build_unified_fluxlit_asgi_app

    captured: dict[str, dict[str, object]] = {}

    class Proc:
        def poll(self) -> None:
            return None

    def popen(cmd: list[str], **kwargs: object) -> Proc:
        captured["kwargs"] = kwargs
        return Proc()

    async def gateway(scope, receive, send) -> None:
        return None

    monkeypatch.setattr("fluxlit.runtime.lifespan_bridge.sys.platform", "win32")
    monkeypatch.setattr(
        "fluxlit.runtime.lifespan_bridge.subprocess.CREATE_NEW_PROCESS_GROUP", 99, raising=False
    )
    monkeypatch.setattr("fluxlit.runtime.lifespan_bridge.subprocess.Popen", popen)
    monkeypatch.setattr(
        "fluxlit.runtime.lifespan_bridge._invoke_wait_for_tcp", lambda *a, **k: None
    )
    monkeypatch.setattr("fluxlit.runtime.lifespan_bridge._terminate_process", lambda *a, **k: None)
    app = build_unified_fluxlit_asgi_app(
        FluxLit(),
        gateway_app=gateway,
        cmd=["streamlit"],
        env={},
        streamlit_port=8501,
        upstream_url_box=[""],
    )
    messages = [
        {"type": "lifespan.startup"},
        {"type": "lifespan.startup"},
        {"type": "lifespan.unknown"},
        {"type": "lifespan.shutdown"},
    ]
    sent: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        return messages.pop(0)

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    await app({"type": "lifespan"}, receive, send)
    assert captured["kwargs"]["creationflags"] == 99
    assert {"type": "lifespan.startup.complete"} in sent
    assert {"type": "lifespan.shutdown.complete"} in sent


@pytest.mark.asyncio
async def test_lifespan_bridge_terminates_started_process_on_wait_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fluxlit import FluxLit
    from fluxlit.runtime.lifespan_bridge import build_unified_fluxlit_asgi_app

    terminated: list[tuple[object, float]] = []

    class Proc:
        def poll(self) -> None:
            return None

    async def gateway(scope, receive, send) -> None:
        return None

    monkeypatch.setattr("fluxlit.runtime.lifespan_bridge.subprocess.Popen", lambda *a, **k: Proc())
    monkeypatch.setattr(
        "fluxlit.runtime.lifespan_bridge._invoke_wait_for_tcp",
        lambda *a, **k: (_ for _ in ()).throw(TimeoutError("no tcp")),
    )
    monkeypatch.setattr(
        "fluxlit.runtime.lifespan_bridge._terminate_process",
        lambda proc, timeout_s: terminated.append((proc, timeout_s)),
    )
    app = build_unified_fluxlit_asgi_app(
        FluxLit(),
        gateway_app=gateway,
        cmd=["streamlit"],
        env={},
        streamlit_port=8501,
        upstream_url_box=["old"],
    )
    sent: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        return {"type": "lifespan.startup"}

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    await app({"type": "lifespan"}, receive, send)
    assert sent == [{"type": "lifespan.startup.failed", "message": "no tcp"}]
    assert terminated and terminated[0][1] == 2.0


@pytest.mark.asyncio
async def test_lifespan_bridge_inner_startup_failure_terminates_sidecar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fluxlit import FluxLit
    from fluxlit.runtime.lifespan_bridge import build_unified_fluxlit_asgi_app

    fl = FluxLit()

    async def broken_api(scope, receive, send) -> None:
        raise RuntimeError("inner boom")

    fl.api = broken_api  # type: ignore[assignment]
    terminated: list[float] = []

    class Proc:
        def poll(self) -> None:
            return None

    async def gateway(scope, receive, send) -> None:
        return None

    monkeypatch.setattr("fluxlit.runtime.lifespan_bridge.subprocess.Popen", lambda *a, **k: Proc())
    monkeypatch.setattr(
        "fluxlit.runtime.lifespan_bridge._invoke_wait_for_tcp", lambda *a, **k: None
    )
    monkeypatch.setattr(
        "fluxlit.runtime.lifespan_bridge._terminate_process",
        lambda proc, timeout_s: terminated.append(timeout_s),
    )
    app = build_unified_fluxlit_asgi_app(
        fl,
        gateway_app=gateway,
        cmd=["streamlit"],
        env={},
        streamlit_port=8501,
        upstream_url_box=[""],
    )
    sent: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        return {"type": "lifespan.startup"}

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    await app({"type": "lifespan"}, receive, send)
    assert sent == [{"type": "lifespan.startup.failed", "message": "inner boom"}]
    assert terminated == [2.0]


@pytest.mark.asyncio
async def test_lifespan_bridge_shutdown_before_startup_completes() -> None:
    from fluxlit import FluxLit
    from fluxlit.runtime.lifespan_bridge import build_unified_fluxlit_asgi_app

    async def gateway(scope, receive, send) -> None:
        return None

    app = build_unified_fluxlit_asgi_app(
        FluxLit(),
        gateway_app=gateway,
        cmd=["streamlit"],
        env={},
        streamlit_port=8501,
        upstream_url_box=[""],
    )
    sent: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        return {"type": "lifespan.shutdown"}

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    await app({"type": "lifespan"}, receive, send)
    assert sent == [{"type": "lifespan.shutdown.complete"}]


@pytest.mark.asyncio
async def test_lifespan_bridge_websocket_when_sidecar_down_closes() -> None:
    from fluxlit import FluxLit
    from fluxlit.runtime.lifespan_bridge import build_unified_fluxlit_asgi_app

    async def gateway(scope, receive, send) -> None:
        raise AssertionError("gateway should not run")

    app = build_unified_fluxlit_asgi_app(
        FluxLit(),
        gateway_app=gateway,
        cmd=["streamlit"],
        env={},
        streamlit_port=8501,
        upstream_url_box=[""],
    )
    sent: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        return {"type": "websocket.connect"}

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    await app({"type": "websocket", "path": "/_stcore/stream"}, receive, send)
    assert sent == [
        {
            "type": "websocket.close",
            "code": 1013,
            "reason": "FluxLit Streamlit sidecar is not running.",
        }
    ]


@pytest.mark.asyncio
async def test_lifespan_bridge_delegates_to_gateway_when_upstream_is_set() -> None:
    from fluxlit import FluxLit
    from fluxlit.runtime.lifespan_bridge import build_unified_fluxlit_asgi_app

    async def gateway(scope, receive, send) -> None:
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    app = build_unified_fluxlit_asgi_app(
        FluxLit(),
        gateway_app=gateway,
        cmd=["streamlit"],
        env={},
        streamlit_port=8501,
        upstream_url_box=["http://127.0.0.1:8501"],
    )
    sent: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    await app({"type": "http", "path": "/"}, receive, send)
    assert sent[0]["status"] == 204


@pytest.mark.asyncio
async def test_asgi_from_fluxlit_resolves_upstream_after_lifespan_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fluxlit import FluxLit
    from fluxlit.runtime import asgi_from_fluxlit

    class Proc:
        def poll(self) -> None:
            return None

        def send_signal(self, sig: object) -> None:
            return None

        def wait(self, timeout: float | None = None) -> int:
            return 0

        def terminate(self) -> None:
            return None

        def kill(self) -> None:
            return None

    monkeypatch.setattr("fluxlit.runtime.lifespan_bridge.subprocess.Popen", lambda *a, **k: Proc())
    monkeypatch.setattr(
        "fluxlit.runtime.lifespan_bridge._invoke_wait_for_tcp", lambda *a, **k: None
    )
    app = asgi_from_fluxlit(FluxLit(), "tests.e2e.minimal_app:app")
    incoming: asyncio.Queue[dict[str, object]] = asyncio.Queue()
    sent: list[dict[str, object]] = []

    async def receive_lifespan() -> dict[str, object]:
        return await incoming.get()

    async def send_lifespan(message: dict[str, object]) -> None:
        sent.append(message)

    task = asyncio.create_task(app({"type": "lifespan"}, receive_lifespan, send_lifespan))
    await incoming.put({"type": "lifespan.startup"})
    for _ in range(20):
        if {"type": "lifespan.startup.complete"} in sent:
            break
        await asyncio.sleep(0)
    assert {"type": "lifespan.startup.complete"} in sent

    http_sent: list[dict[str, object]] = []

    async def receive_http() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send_http(message: dict[str, object]) -> None:
        http_sent.append(message)

    await app(
        {"type": "http", "method": "GET", "path": "/streamlit", "headers": [], "query_string": b""},
        receive_http,
        send_http,
    )
    assert http_sent[0]["status"] == 502
    await incoming.put({"type": "lifespan.shutdown"})
    await task


def test_run_unified_rejects_invalid_reload_scope_before_spawning_streamlit() -> None:
    """Invalid ``reload_scope`` must fail before starting the Streamlit subprocess."""
    with pytest.raises(ValueError, match="reload_scope"):
        run_unified("tests.e2e.minimal_app:app", reload=True, reload_scope="not-a-scope")


def test_run_unified_plain_configures_gateway_and_cleans_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fluxlit.runtime.uvicorn_runner as runner

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FLUXLIT_NO_PIDFILE", "1")
    monkeypatch.setattr(runner, "find_free_port", lambda: 8765)
    monkeypatch.setattr(runner, "_invoke_wait_for_tcp", lambda *a, **k: None)
    captures: dict[str, object] = {"terminated": 0}

    class Proc:
        def wait(self) -> int:
            return 0

        def poll(self) -> None:
            return None

        def send_signal(self, sig: object) -> None:
            return None

        def terminate(self) -> None:
            return None

        def kill(self) -> None:
            return None

    def fake_popen(cmd: list[str], **kwargs: object) -> Proc:
        captures["cmd"] = cmd
        captures["popen_kwargs"] = kwargs
        return Proc()

    class Config:
        def __init__(self, app: object, **kwargs: object) -> None:
            captures["config_app"] = app
            captures["config_kwargs"] = kwargs

    class Server:
        def __init__(self, config: Config) -> None:
            self.config = config
            self.should_exit = False

        def run(self) -> None:
            captures["server_ran"] = True

    class ImmediateThread:
        def __init__(self, target, daemon: bool) -> None:
            self.target = target

        def start(self) -> None:
            self.target()

    monkeypatch.setattr(runner.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(runner.uvicorn, "Config", Config)
    monkeypatch.setattr(runner.uvicorn, "Server", Server)
    monkeypatch.setattr(runner.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(
        runner,
        "_terminate_process",
        lambda proc: captures.__setitem__("terminated", captures["terminated"] + 1),
    )

    run_unified(
        "tests.e2e.minimal_app:app",
        host="0.0.0.0",
        port=8001,
        proxy_headers=True,
        forwarded_allow_ips="127.0.0.1",
    )

    assert captures["server_ran"] is True
    assert captures["terminated"] == 1
    assert "--server.port" in captures["cmd"]
    kwargs = captures["config_kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["host"] == "0.0.0.0"
    assert kwargs["port"] == 8001
    assert kwargs["proxy_headers"] is True
    assert kwargs["forwarded_allow_ips"] == "127.0.0.1"


def test_run_unified_debug_writes_fluxlit_debug_banner_to_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    import fluxlit.runtime.uvicorn_runner as runner

    (tmp_path / "dbg_run_app.py").write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n"
        "app = FluxLit(title='D', settings=FluxlitSettings(debug=True))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FLUXLIT_NO_PIDFILE", "1")
    monkeypatch.setattr(runner, "find_free_port", lambda: 8765)
    monkeypatch.setattr(runner, "_invoke_wait_for_tcp", lambda *a, **k: None)
    captures: dict[str, object] = {"terminated": 0}

    class Proc:
        def wait(self) -> int:
            return 0

        def poll(self) -> None:
            return None

        def send_signal(self, sig: object) -> None:
            return None

        def terminate(self) -> None:
            return None

        def kill(self) -> None:
            return None

    def fake_popen(cmd: list[str], **kwargs: object) -> Proc:
        captures["cmd"] = cmd
        captures["popen_kwargs"] = kwargs
        return Proc()

    class Config:
        def __init__(self, app: object, **kwargs: object) -> None:
            captures["config_app"] = app
            captures["config_kwargs"] = kwargs

    class Server:
        def __init__(self, config: Config) -> None:
            self.config = config
            self.should_exit = False

        def run(self) -> None:
            captures["server_ran"] = True

    class ImmediateThread:
        def __init__(self, target, daemon: bool) -> None:
            self.target = target

        def start(self) -> None:
            self.target()

    monkeypatch.setattr(runner.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(runner.uvicorn, "Config", Config)
    monkeypatch.setattr(runner.uvicorn, "Server", Server)
    monkeypatch.setattr(runner.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(
        runner,
        "_terminate_process",
        lambda proc: captures.__setitem__("terminated", captures["terminated"] + 1),
    )

    run_unified("dbg_run_app:app", host="127.0.0.1", port=8002)
    err = capfd.readouterr().err
    assert "[fluxlit-debug]" in err
    assert "internal_api_base" in err


def test_run_unified_workbench_writes_banner_and_enables_proxy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import fluxlit.runtime.uvicorn_runner as runner

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FLUXLIT_NO_PIDFILE", "1")
    monkeypatch.setattr(runner, "find_free_port", lambda: 8765)
    monkeypatch.setattr(runner, "_invoke_wait_for_tcp", lambda *a, **k: None)
    captures: dict[str, object] = {"terminated": 0, "kwargs": {}}

    class Proc:
        def wait(self) -> int:
            return 0

        def poll(self) -> None:
            return None

        def send_signal(self, sig: object) -> None:
            return None

        def terminate(self) -> None:
            return None

        def kill(self) -> None:
            return None

    def fake_popen(cmd: list[str], **kwargs: object) -> Proc:
        return Proc()

    class Config:
        def __init__(self, app: object, **kwargs: object) -> None:
            captures["kwargs"] = kwargs

    class Server:
        def __init__(self, config: Config) -> None:
            self.config = config
            self.should_exit = False

        def run(self) -> None:
            return None

    class ImmediateThread:
        def __init__(self, target, daemon: bool) -> None:
            self.target = target

        def start(self) -> None:
            self.target()

    monkeypatch.setattr(runner.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(runner.uvicorn, "Config", Config)
    monkeypatch.setattr(runner.uvicorn, "Server", Server)
    monkeypatch.setattr(runner.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(
        runner,
        "_terminate_process",
        lambda proc: captures.__setitem__("terminated", captures["terminated"] + 1),
    )

    run_unified(
        "tests.e2e.minimal_app:app",
        host="127.0.0.1",
        port=8002,
        proxy_headers=False,
        workbench_mode=True,
    )
    err = capsys.readouterr().err
    assert "Workbench/Connect mode" in err
    assert ":8002" in err and "healthz" in err
    kw = captures["kwargs"]
    assert isinstance(kw, dict)
    assert kw.get("proxy_headers") is True


def test_run_unified_reload_full_restarts_streamlit_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import fluxlit.runtime.uvicorn_runner as runner

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FLUXLIT_NO_PIDFILE", "1")
    ports = iter([8765, 8766])
    monkeypatch.setattr(runner, "find_free_port", lambda: next(ports))
    monkeypatch.setattr(runner, "_invoke_wait_for_tcp", lambda *a, **k: None)
    captures: dict[str, object] = {"terminated": 0, "popen_count": 0}

    class Proc:
        def wait(self) -> int:
            return 0

        def poll(self) -> None:
            return None

    def fake_popen(cmd: list[str], **kwargs: object) -> Proc:
        captures["popen_count"] = captures["popen_count"] + 1
        captures["last_cmd"] = cmd
        return Proc()

    class Config:
        def __init__(self, app: object, **kwargs: object) -> None:
            captures["config_app"] = app
            captures["config_kwargs"] = kwargs

    class Server:
        def __init__(self, config: Config) -> None:
            self.config = config
            self.should_exit = False

        def run(self) -> None:
            captures["server_ran"] = True

    class NoopThread:
        def __init__(self, target, daemon: bool) -> None:
            self.target = target

        def start(self) -> None:
            return None

    def fake_start_watcher(on_change, *, debounce_s: float, stop_flag) -> None:
        captures["watcher_debounce"] = debounce_s
        on_change()

    monkeypatch.setattr(runner.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(runner.uvicorn, "Config", Config)
    monkeypatch.setattr(runner.uvicorn, "Server", Server)
    monkeypatch.setattr(runner.threading, "Thread", NoopThread)
    monkeypatch.setattr(runner, "_start_streamlit_reload_watcher", fake_start_watcher)
    monkeypatch.setattr(
        runner,
        "_terminate_process",
        lambda proc: captures.__setitem__("terminated", captures["terminated"] + 1),
    )

    run_unified("tests.e2e.minimal_app:app", reload=True, reload_scope="full")

    assert captures["server_ran"] is True
    assert captures["popen_count"] == 2
    assert captures["terminated"] == 2
    assert captures["watcher_debounce"] == 0.25
    kwargs = captures["config_kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["factory"] is True
    assert kwargs["reload"] is True
    assert "reload-scope=full" in capsys.readouterr().err


def test_run_unified_reload_full_timeout_stops_gateway(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fluxlit.runtime.uvicorn_runner as runner

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FLUXLIT_NO_PIDFILE", "1")
    ports = iter([8765, 8766])
    monkeypatch.setattr(runner, "find_free_port", lambda: next(ports))
    calls = {"waits": 0, "terminated": 0}

    def wait_tcp(*args: object, **kwargs: object) -> None:
        calls["waits"] += 1
        if calls["waits"] == 2:
            raise TimeoutError("no listen")

    class Proc:
        def wait(self) -> int:
            return 0

        def poll(self) -> None:
            return None

    class Config:
        def __init__(self, app: object, **kwargs: object) -> None:
            return None

    class Server:
        last: Server | None = None

        def __init__(self, config: Config) -> None:
            self.config = config
            self.should_exit = False
            Server.last = self

        def run(self) -> None:
            return None

    class NoopThread:
        def __init__(self, target, daemon: bool) -> None:
            self.target = target

        def start(self) -> None:
            return None

    monkeypatch.setattr(runner, "_invoke_wait_for_tcp", wait_tcp)
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *a, **k: Proc())
    monkeypatch.setattr(runner.uvicorn, "Config", Config)
    monkeypatch.setattr(runner.uvicorn, "Server", Server)
    monkeypatch.setattr(runner.threading, "Thread", NoopThread)
    monkeypatch.setattr(
        runner,
        "_start_streamlit_reload_watcher",
        lambda on_change, **kwargs: on_change(),
    )
    monkeypatch.setattr(
        runner,
        "_terminate_process",
        lambda proc: calls.__setitem__("terminated", calls["terminated"] + 1),
    )

    run_unified("tests.e2e.minimal_app:app", reload=True, reload_scope="full")

    assert Server.last is not None
    assert Server.last.should_exit is True
    assert calls["terminated"] == 3


def test_run_unified_windows_pidfile_trust_proxy_and_grace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fluxlit.runtime.uvicorn_runner as runner

    (tmp_path / "run_app.py").write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n"
        "app = FluxLit(settings=FluxlitSettings(\n"
        "    trust_proxy=True,\n"
        "    forwarded_allow_ips='10.0.0.1',\n"
        "    uvicorn_graceful_shutdown_timeout_s=12,\n"
        "))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FLUXLIT_NO_PIDFILE", raising=False)
    monkeypatch.setattr(runner.sys, "platform", "win32")
    monkeypatch.setattr(runner.subprocess, "CREATE_NEW_PROCESS_GROUP", 512, raising=False)
    monkeypatch.setattr(runner, "find_free_port", lambda: 8765)
    monkeypatch.setattr(runner, "_invoke_wait_for_tcp", lambda *a, **k: None)
    captures: dict[str, object] = {}

    class Proc:
        def wait(self) -> int:
            return 0

        def poll(self) -> None:
            return None

    def fake_popen(cmd: list[str], **kwargs: object) -> Proc:
        captures["popen_kwargs"] = kwargs
        return Proc()

    class Config:
        def __init__(self, app: object, **kwargs: object) -> None:
            captures["config_kwargs"] = kwargs

    class Server:
        def __init__(self, config: Config) -> None:
            self.config = config
            self.should_exit = False

        def run(self) -> None:
            return None

    class NoopThread:
        def __init__(self, target, daemon: bool) -> None:
            self.target = target

        def start(self) -> None:
            return None

    monkeypatch.setattr(runner.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(runner.uvicorn, "Config", Config)
    monkeypatch.setattr(runner.uvicorn, "Server", Server)
    monkeypatch.setattr(runner.threading, "Thread", NoopThread)
    monkeypatch.setattr(runner, "_terminate_process", lambda proc: None)

    run_unified("run_app:app")

    popen_kwargs = captures["popen_kwargs"]
    assert isinstance(popen_kwargs, dict)
    assert popen_kwargs["creationflags"] == 512
    kwargs = captures["config_kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["proxy_headers"] is True
    assert kwargs["forwarded_allow_ips"] == "10.0.0.1"
    assert kwargs["timeout_graceful_shutdown"] == 12
    assert not (tmp_path / ".fluxlit-dev.pid").exists()


def test_run_unified_reload_gateway_message_and_grace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import fluxlit.runtime.uvicorn_runner as runner

    (tmp_path / "reload_app.py").write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n"
        "app = FluxLit(settings=FluxlitSettings(uvicorn_graceful_shutdown_timeout_s=7))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FLUXLIT_NO_PIDFILE", "1")
    monkeypatch.setattr(runner, "find_free_port", lambda: 8765)
    monkeypatch.setattr(runner, "_invoke_wait_for_tcp", lambda *a, **k: None)
    captures: dict[str, object] = {}

    class Proc:
        def wait(self) -> int:
            return 0

        def poll(self) -> None:
            return None

    class Config:
        def __init__(self, app: object, **kwargs: object) -> None:
            captures["config_app"] = app
            captures["config_kwargs"] = kwargs

    class Server:
        def __init__(self, config: Config) -> None:
            self.config = config
            self.should_exit = False

        def run(self) -> None:
            return None

    class NoopThread:
        def __init__(self, target, daemon: bool) -> None:
            self.target = target

        def start(self) -> None:
            return None

    monkeypatch.setattr(runner.subprocess, "Popen", lambda *a, **k: Proc())
    monkeypatch.setattr(runner.uvicorn, "Config", Config)
    monkeypatch.setattr(runner.uvicorn, "Server", Server)
    monkeypatch.setattr(runner.threading, "Thread", NoopThread)
    monkeypatch.setattr(runner, "_terminate_process", lambda proc: None)

    run_unified("reload_app:app", reload=True, reload_scope="gateway")

    assert captures["config_app"] == "fluxlit.runtime:create_gateway_app"
    kwargs = captures["config_kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["timeout_graceful_shutdown"] == 7
    assert "reload-scope=gateway" in capsys.readouterr().err


def test_run_unified_monitor_handles_intentional_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fluxlit.runtime.uvicorn_runner as runner

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FLUXLIT_NO_PIDFILE", "1")
    ports = iter([8765, 8766])
    monkeypatch.setattr(runner, "find_free_port", lambda: next(ports))
    monkeypatch.setattr(runner, "_invoke_wait_for_tcp", lambda *a, **k: None)
    captures: dict[str, object] = {"popen_count": 0}
    monitor_target = {"fn": None}

    class Proc:
        def wait(self) -> int:
            return 0

        def poll(self) -> None:
            return None

    class Config:
        def __init__(self, app: object, **kwargs: object) -> None:
            return None

    class Server:
        def __init__(self, config: Config) -> None:
            self.config = config
            self.should_exit = False

        def run(self) -> None:
            assert monitor_target["fn"] is not None
            monitor_target["fn"]()
            captures["server_should_exit"] = self.should_exit

    class CapturingThread:
        def __init__(self, target, daemon: bool) -> None:
            monitor_target["fn"] = target

        def start(self) -> None:
            return None

    def fake_popen(cmd: list[str], **kwargs: object) -> Proc:
        captures["popen_count"] = captures["popen_count"] + 1
        return Proc()

    monkeypatch.setattr(runner.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(runner.uvicorn, "Config", Config)
    monkeypatch.setattr(runner.uvicorn, "Server", Server)
    monkeypatch.setattr(runner.threading, "Thread", CapturingThread)
    monkeypatch.setattr(
        runner,
        "_start_streamlit_reload_watcher",
        lambda on_change, **kwargs: on_change(),
    )
    monkeypatch.setattr(runner, "_terminate_process", lambda proc: None)

    run_unified("tests.e2e.minimal_app:app", reload=True, reload_scope="full")

    assert captures["popen_count"] == 2
    assert captures["server_should_exit"] is True


def test_create_gateway_app_rejects_empty_upstream(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "empty_up_app.py").write_text(
        "from fluxlit import FluxLit\napp = FluxLit(title='E')\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv("FLUXLIT_APP", "empty_up_app:app")
    monkeypatch.setenv("FLUXLIT_STREAMLIT_UPSTREAM", "")
    monkeypatch.delenv("FLUXLIT_STREAMLIT_UPSTREAM_FILE", raising=False)
    with pytest.raises(RuntimeError, match="upstream"):
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


def test_create_gateway_app_honors_fluxlit_root_path_for_both_upstream_shapes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``create_gateway_app`` wraps like ``fluxlit run``: strip- and full-path URLs work."""
    (tmp_path / "cg_mount.py").write_text(
        "from fluxlit import FluxLit\napp = FluxLit(title='M')\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv("FLUXLIT_APP", "cg_mount:app")
    monkeypatch.setenv("FLUXLIT_STREAMLIT_UPSTREAM", "http://127.0.0.1:9")
    monkeypatch.setenv("FLUXLIT_API_PREFIX", "/api")
    monkeypatch.setenv("FLUXLIT_ROOT_PATH", "/content/99")

    asgi = create_gateway_app()
    client = TestClient(asgi)
    assert client.get("/api/healthz").status_code == 200
    assert client.get("/content/99/api/healthz").status_code == 200
    assert client.get("/content/99/nope-streamlit").status_code == 502


def test_default_pidfile_path_cwd_and_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert default_pidfile_path() == tmp_path / ".fluxlit-dev.pid"
    monkeypatch.setenv("FLUXLIT_PIDFILE", str(tmp_path / "via_env.pid"))
    assert default_pidfile_path() == tmp_path / "via_env.pid"
    monkeypatch.delenv("FLUXLIT_PIDFILE", raising=False)
    assert default_pidfile_path(tmp_path / "custom.pid") == tmp_path / "custom.pid"


def test_write_and_remove_pidfile(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "app.pid"
    _write_pidfile(path)
    assert path.read_text(encoding="ascii").strip() == str(os.getpid())
    _remove_pidfile(path)
    assert not path.exists()
    _remove_pidfile(path)


def test_resolve_import_target_for_unified_prefers_explicit_and_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fl = FluxLit(import_target=" explicit:app ")
    assert resolve_import_target_for_unified(fl) == "explicit:app"

    fl = FluxLit()
    monkeypatch.setenv("FLUXLIT_APP", "env_app:app")
    assert resolve_import_target_for_unified(fl) == "env_app:app"


def test_resolve_import_target_for_unified_falls_back_to_project_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "fluxlit.toml").write_text('target = "configured:app"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FLUXLIT_APP", raising=False)
    assert resolve_import_target_for_unified(FluxLit()) == "configured:app"


def test_gateway_bind_for_streamlit_child_uses_project_and_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fluxlit.runtime.resolve import _gateway_bind_for_streamlit_child

    (tmp_path / "fluxlit.toml").write_text(
        'gateway_host = "0.0.0.0"\ngateway_port = 9100\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    fl = FluxLit()
    assert _gateway_bind_for_streamlit_child(fl) == ("0.0.0.0", 9100)
    monkeypatch.setenv("FLUXLIT_GATEWAY_HOST", "127.0.0.2")
    monkeypatch.setenv("FLUXLIT_GATEWAY_PORT", "not-int")
    assert _gateway_bind_for_streamlit_child(fl) == ("127.0.0.2", fl.settings.gateway_port)
    monkeypatch.setenv("FLUXLIT_GATEWAY_PORT", "9200")
    assert _gateway_bind_for_streamlit_child(fl) == ("127.0.0.2", 9200)


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


def test_pid_is_zombie_unix_handles_subprocess_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise OSError("ps missing")

    monkeypatch.setattr("fluxlit.runtime.process_control.subprocess.run", boom)
    assert _pid_is_zombie_unix(123) is False


def test_pid_is_zombie_unix_detects_z_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "fluxlit.runtime.process_control.subprocess.run",
        lambda *a, **k: subprocess.CompletedProcess(args=[], returncode=0, stdout="Z+\n"),
    )
    assert _pid_is_zombie_unix(123) is True


def test_pid_is_zombie_unix_nonzero_ps_return(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "fluxlit.runtime.process_control.subprocess.run",
        lambda *a, **k: subprocess.CompletedProcess(args=[], returncode=1, stdout=""),
    )
    assert _pid_is_zombie_unix(123) is False


def test_pid_running_permission_error_is_running(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("fluxlit.runtime.process_control.sys.platform", "linux")

    def deny(pid: int, sig: int) -> None:
        raise PermissionError("denied")

    monkeypatch.setattr("fluxlit.runtime.process_control.os.kill", deny)
    assert _pid_running(123) is True


def test_pid_running_process_lookup_is_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("fluxlit.runtime.process_control.sys.platform", "linux")

    def missing(pid: int, sig: int) -> None:
        raise ProcessLookupError("missing")

    monkeypatch.setattr("fluxlit.runtime.process_control.os.kill", missing)
    assert _pid_running(123) is False


def test_pid_running_zombie_is_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("fluxlit.runtime.process_control.sys.platform", "linux")
    monkeypatch.setattr("fluxlit.runtime.process_control.os.kill", lambda pid, sig: None)
    monkeypatch.setattr("fluxlit.runtime.process_control._pid_is_zombie_unix", lambda pid: True)
    assert _pid_running(123) is False


def test_pid_running_windows_active_and_access_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    import ctypes

    monkeypatch.setattr("fluxlit.runtime.process_control.sys.platform", "win32")

    class Kernel32:
        def __init__(self) -> None:
            self.last_error = 5

        def OpenProcess(self, access: int, inherit: bool, pid: int) -> int:
            return 1 if pid == 123 else 0

        def GetExitCodeProcess(self, handle: int, out) -> int:
            out._obj.value = 259
            return 1

        def CloseHandle(self, handle: int) -> None:
            return None

        def GetLastError(self) -> int:
            return self.last_error

    monkeypatch.setattr(ctypes, "windll", types.SimpleNamespace(kernel32=Kernel32()), raising=False)
    assert _pid_running(123) is True
    assert _pid_running(456) is True


def test_pid_running_windows_exit_code_query_failure_is_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import ctypes

    monkeypatch.setattr("fluxlit.runtime.process_control.sys.platform", "win32")

    class Kernel32:
        def OpenProcess(self, access: int, inherit: bool, pid: int) -> int:
            return 1

        def GetExitCodeProcess(self, handle: int, out) -> int:
            return 0

        def CloseHandle(self, handle: int) -> None:
            return None

        def GetLastError(self) -> int:
            return 0

    monkeypatch.setattr(ctypes, "windll", types.SimpleNamespace(kernel32=Kernel32()), raising=False)
    assert _pid_running(123) is True


def test_windows_taskkill_tree_builds_force_command(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr("fluxlit.runtime.process_control.subprocess.run", fake_run)
    result = _windows_taskkill_tree(123, force=True)
    assert result.returncode == 0
    assert captured["cmd"] == ["taskkill", "/PID", "123", "/T", "/F"]


def test_shutdown_unified_process_permission_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid_path = tmp_path / "denied.pid"
    pid_path.write_text("123\n", encoding="ascii")
    monkeypatch.setattr("fluxlit.runtime.process_control.sys.platform", "linux")
    monkeypatch.setattr("fluxlit.runtime.process_control._pid_running", lambda pid: True)

    def deny(pid: int, sig: int) -> None:
        raise PermissionError("denied")

    monkeypatch.setattr("fluxlit.runtime.process_control.os.kill", deny)
    code, msg = shutdown_unified_process(pid_path)
    assert code == 1
    assert "Cannot signal" in msg


def test_shutdown_unified_process_process_lookup_during_signal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid_path = tmp_path / "gone.pid"
    pid_path.write_text("123\n", encoding="ascii")
    monkeypatch.setattr("fluxlit.runtime.process_control.sys.platform", "linux")
    monkeypatch.setattr("fluxlit.runtime.process_control._pid_running", lambda pid: True)

    def gone(pid: int, sig: int) -> None:
        raise ProcessLookupError("gone")

    monkeypatch.setattr("fluxlit.runtime.process_control.os.kill", gone)
    code, msg = shutdown_unified_process(pid_path)
    assert code == 0
    assert "exited before signal" in msg
    assert not pid_path.exists()


def test_shutdown_unified_process_force_kills_after_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid_path = tmp_path / "force.pid"
    pid_path.write_text("123\n", encoding="ascii")
    monkeypatch.setattr("fluxlit.runtime.process_control.sys.platform", "linux")
    sigkill = getattr(signal, "SIGKILL", signal.SIGTERM)
    monkeypatch.setattr("fluxlit.runtime.process_control.signal.SIGKILL", sigkill, raising=False)
    states = iter([True, True, False])
    monkeypatch.setattr("fluxlit.runtime.process_control._pid_running", lambda pid: next(states))
    signals: list[int] = []
    monkeypatch.setattr(
        "fluxlit.runtime.process_control.os.kill", lambda pid, sig: signals.append(sig)
    )
    monkeypatch.setattr("fluxlit.runtime.process_control.time.sleep", lambda s: None)
    clock = {"t": 0.0}

    def monotonic() -> float:
        clock["t"] += 1.0
        return clock["t"]

    monkeypatch.setattr("fluxlit.runtime.process_control.time.monotonic", monotonic)
    code, msg = shutdown_unified_process(pid_path, force=True, wait_s=0.1)
    assert code == 0
    assert "process 123" in msg
    assert signal.SIGTERM in signals
    assert sigkill in signals


def test_shutdown_unified_process_stops_during_wait(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid_path = tmp_path / "stops.pid"
    pid_path.write_text("123\n", encoding="ascii")
    states = iter([True, True, False])
    monkeypatch.setattr("fluxlit.runtime.process_control.sys.platform", "linux")
    monkeypatch.setattr("fluxlit.runtime.process_control._pid_running", lambda pid: next(states))
    monkeypatch.setattr("fluxlit.runtime.process_control.os.kill", lambda pid, sig: None)
    monkeypatch.setattr("fluxlit.runtime.process_control.time.sleep", lambda s: None)
    code, msg = shutdown_unified_process(pid_path, wait_s=1.0)
    assert code == 0
    assert "Stopped process" in msg
    assert not pid_path.exists()


def test_shutdown_unified_process_still_running_after_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid_path = tmp_path / "running.pid"
    pid_path.write_text("123\n", encoding="ascii")
    monkeypatch.setattr("fluxlit.runtime.process_control.sys.platform", "linux")
    monkeypatch.setattr("fluxlit.runtime.process_control._pid_running", lambda pid: True)
    monkeypatch.setattr("fluxlit.runtime.process_control.os.kill", lambda pid, sig: None)
    monkeypatch.setattr("fluxlit.runtime.process_control.time.sleep", lambda s: None)
    times = iter([0.0, 1.0, 1.1, 1.2, 1.3])

    def monotonic() -> float:
        return next(times)

    monkeypatch.setattr("fluxlit.runtime.process_control.time.monotonic", monotonic)
    code, msg = shutdown_unified_process(pid_path, force=False, wait_s=0.1)
    assert code == 1
    assert "still running" in msg


def test_shutdown_unified_process_final_stopped_after_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid_path = tmp_path / "final.pid"
    pid_path.write_text("123\n", encoding="ascii")
    states = iter([True, False])
    monkeypatch.setattr("fluxlit.runtime.process_control.sys.platform", "linux")
    monkeypatch.setattr("fluxlit.runtime.process_control._pid_running", lambda pid: next(states))
    monkeypatch.setattr("fluxlit.runtime.process_control.os.kill", lambda pid, sig: None)
    monkeypatch.setattr("fluxlit.runtime.process_control.time.sleep", lambda s: None)
    clock = {"t": 0.0}

    def monotonic() -> float:
        clock["t"] += 1.0
        return clock["t"]

    monkeypatch.setattr("fluxlit.runtime.process_control.time.monotonic", monotonic)
    code, msg = shutdown_unified_process(pid_path, force=False, wait_s=0.1)
    assert code == 0
    assert "Stopped process" in msg


def test_shutdown_unified_process_windows_taskkill_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid_path = tmp_path / "win.pid"
    pid_path.write_text("123\n", encoding="ascii")
    monkeypatch.setattr("fluxlit.runtime.process_control.sys.platform", "win32")
    monkeypatch.setattr("fluxlit.runtime.process_control._pid_running", lambda pid: True)

    def os_kill(pid: int, sig: int) -> None:
        raise RuntimeError("no sigterm")

    monkeypatch.setattr("fluxlit.runtime.process_control.os.kill", os_kill)
    monkeypatch.setattr(
        "fluxlit.runtime.process_control._windows_taskkill_tree",
        lambda pid, force: subprocess.CompletedProcess([], 1, stdout="", stderr="not found"),
    )
    code, msg = shutdown_unified_process(pid_path)
    assert code == 0
    assert "exited before signal" in msg


def test_shutdown_unified_process_windows_process_lookup_during_signal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid_path = tmp_path / "win-gone.pid"
    pid_path.write_text("123\n", encoding="ascii")
    monkeypatch.setattr("fluxlit.runtime.process_control.sys.platform", "win32")
    monkeypatch.setattr("fluxlit.runtime.process_control._pid_running", lambda pid: True)

    def gone(pid: int, sig: int) -> None:
        raise ProcessLookupError("gone")

    monkeypatch.setattr("fluxlit.runtime.process_control.os.kill", gone)
    code, msg = shutdown_unified_process(pid_path)
    assert code == 0
    assert "exited before signal" in msg
    assert not pid_path.exists()


def test_shutdown_unified_process_wait_loop_sleeps_before_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid_path = tmp_path / "sleep-before-stop.pid"
    pid_path.write_text("123\n", encoding="ascii")
    monkeypatch.setattr("fluxlit.runtime.process_control.sys.platform", "linux")
    states = iter([True, True, False])
    monkeypatch.setattr("fluxlit.runtime.process_control._pid_running", lambda pid: next(states))
    monkeypatch.setattr("fluxlit.runtime.process_control.os.kill", lambda pid, sig: None)
    sleeps: list[float] = []
    monkeypatch.setattr("fluxlit.runtime.process_control.time.sleep", lambda s: sleeps.append(s))
    clock = {"t": 0.0}

    def monotonic() -> float:
        clock["t"] += 0.1
        return clock["t"]

    monkeypatch.setattr("fluxlit.runtime.process_control.time.monotonic", monotonic)
    code, msg = shutdown_unified_process(pid_path, wait_s=1.0)
    assert code == 0
    assert "Stopped process" in msg
    assert sleeps == [0.05]


def test_shutdown_unified_process_windows_escalates_without_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid_path = tmp_path / "win-escalate.pid"
    pid_path.write_text("123\n", encoding="ascii")
    monkeypatch.setattr("fluxlit.runtime.process_control.sys.platform", "win32")
    states = iter([True, False])
    monkeypatch.setattr("fluxlit.runtime.process_control._pid_running", lambda pid: next(states))
    monkeypatch.setattr("fluxlit.runtime.process_control.os.kill", lambda pid, sig: None)
    monkeypatch.setattr("fluxlit.runtime.process_control.time.sleep", lambda s: None)
    taskkill_calls: list[bool] = []
    monkeypatch.setattr(
        "fluxlit.runtime.process_control._windows_taskkill_tree",
        lambda pid, force: (
            taskkill_calls.append(force) or subprocess.CompletedProcess([], 0, stdout="", stderr="")
        ),
    )
    times = iter([0.0, 1.0, 1.1, 1.2, 1.3])

    def monotonic() -> float:
        return next(times)

    monkeypatch.setattr("fluxlit.runtime.process_control.time.monotonic", monotonic)
    code, msg = shutdown_unified_process(pid_path, force=False, wait_s=0.1)
    assert code == 0
    assert "Stopped process" in msg
    assert taskkill_calls == [True]


def test_shutdown_unified_process_windows_escalation_loop_stops(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid_path = tmp_path / "win-escalate-loop.pid"
    pid_path.write_text("123\n", encoding="ascii")
    monkeypatch.setattr("fluxlit.runtime.process_control.sys.platform", "win32")
    states = iter([True, True, False])
    monkeypatch.setattr("fluxlit.runtime.process_control._pid_running", lambda pid: next(states))
    monkeypatch.setattr("fluxlit.runtime.process_control.os.kill", lambda pid, sig: None)
    monkeypatch.setattr(
        "fluxlit.runtime.process_control._windows_taskkill_tree",
        lambda pid, force: subprocess.CompletedProcess([], 0, stdout="", stderr=""),
    )
    monkeypatch.setattr("fluxlit.runtime.process_control.time.sleep", lambda s: None)
    times = iter([0.0, 1.0, 1.1, 1.2, 1.3])

    def monotonic() -> float:
        return next(times)

    monkeypatch.setattr("fluxlit.runtime.process_control.time.monotonic", monotonic)
    code, msg = shutdown_unified_process(pid_path, force=False, wait_s=0.1)
    assert code == 0
    assert "Stopped process" in msg
    assert not pid_path.exists()


def test_shutdown_unified_process_windows_force_uses_taskkill(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid_path = tmp_path / "win-force.pid"
    pid_path.write_text("123\n", encoding="ascii")
    monkeypatch.setattr("fluxlit.runtime.process_control.sys.platform", "win32")
    states = iter([True, False])
    monkeypatch.setattr("fluxlit.runtime.process_control._pid_running", lambda pid: next(states))
    monkeypatch.setattr("fluxlit.runtime.process_control.os.kill", lambda pid, sig: None)
    taskkill_calls: list[bool] = []
    monkeypatch.setattr(
        "fluxlit.runtime.process_control._windows_taskkill_tree",
        lambda pid, force: (
            taskkill_calls.append(force) or subprocess.CompletedProcess([], 0, stdout="", stderr="")
        ),
    )
    monkeypatch.setattr("fluxlit.runtime.process_control.time.sleep", lambda s: None)
    clock = {"t": 0.0}

    def monotonic() -> float:
        clock["t"] += 1.0
        return clock["t"]

    monkeypatch.setattr("fluxlit.runtime.process_control.time.monotonic", monotonic)
    code, msg = shutdown_unified_process(pid_path, force=True, wait_s=0.1)
    assert code == 0
    assert "Killed process" in msg
    assert taskkill_calls == [True]


def test_shutdown_unified_process_force_loop_sleeps_before_kill(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid_path = tmp_path / "force-sleep.pid"
    pid_path.write_text("123\n", encoding="ascii")
    monkeypatch.setattr("fluxlit.runtime.process_control.sys.platform", "linux")
    sigkill = getattr(signal, "SIGKILL", signal.SIGTERM)
    monkeypatch.setattr("fluxlit.runtime.process_control.signal.SIGKILL", sigkill, raising=False)
    states = iter([True, True, False])
    monkeypatch.setattr("fluxlit.runtime.process_control._pid_running", lambda pid: next(states))
    monkeypatch.setattr("fluxlit.runtime.process_control.os.kill", lambda pid, sig: None)
    sleeps: list[float] = []
    monkeypatch.setattr("fluxlit.runtime.process_control.time.sleep", lambda s: sleeps.append(s))
    times = iter([0.0, 1.0, 1.1, 1.2, 1.3])

    def monotonic() -> float:
        return next(times)

    monkeypatch.setattr("fluxlit.runtime.process_control.time.monotonic", monotonic)
    code, msg = shutdown_unified_process(pid_path, force=True, wait_s=0.1)
    assert code == 0
    assert "Killed process" in msg
    assert sleeps == [0.05]


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


def test_terminate_process_returns_when_already_exited() -> None:
    class Proc:
        def poll(self) -> int:
            return 0

    _terminate_process(Proc())  # type: ignore[arg-type]


def test_terminate_process_escalates_to_terminate_then_kill() -> None:
    class Proc:
        def __init__(self) -> None:
            self.signals: list[object] = []
            self.terminated = False
            self.killed = False

        def poll(self) -> None:
            return None

        def send_signal(self, sig: object) -> None:
            self.signals.append(sig)

        def wait(self, timeout: float | None = None) -> int:
            raise subprocess.TimeoutExpired("proc", timeout)

        def terminate(self) -> None:
            self.terminated = True

        def kill(self) -> None:
            self.killed = True

    proc = Proc()
    _terminate_process(proc, timeout_s=0.01)  # type: ignore[arg-type]
    assert proc.signals
    assert proc.terminated is True
    assert proc.killed is True


def test_terminate_process_returns_after_terminate() -> None:
    class Proc:
        def __init__(self) -> None:
            self.waits = 0
            self.terminated = False

        def poll(self) -> None:
            return None

        def send_signal(self, sig: object) -> None:
            return None

        def wait(self, timeout: float | None = None) -> int:
            self.waits += 1
            if self.waits == 1:
                raise subprocess.TimeoutExpired("proc", timeout)
            return 0

        def terminate(self) -> None:
            self.terminated = True

        def kill(self) -> None:
            raise AssertionError("should not kill")

    proc = Proc()
    _terminate_process(proc, timeout_s=0.01)  # type: ignore[arg-type]
    assert proc.terminated is True


def test_terminate_process_windows_ctrl_break(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("fluxlit.runtime.streamlit_proc.sys.platform", "win32")

    class Proc:
        def __init__(self) -> None:
            self.signals: list[object] = []

        def poll(self) -> None:
            return None

        def send_signal(self, sig: object) -> None:
            self.signals.append(sig)

        def wait(self, timeout: float | None = None) -> int:
            return 0

        def terminate(self) -> None:
            raise AssertionError("should not terminate")

        def kill(self) -> None:
            raise AssertionError("should not kill")

    monkeypatch.setattr(
        "fluxlit.runtime.streamlit_proc.signal.CTRL_BREAK_EVENT", 999, raising=False
    )
    proc = Proc()
    _terminate_process(proc, timeout_s=0.01)  # type: ignore[arg-type]
    assert proc.signals == [999]


def test_reload_watcher_import_error_message(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    from fluxlit.runtime.reload_watcher import _start_streamlit_reload_watcher

    real_import = __import__

    def fake_import(name: str, *args: object, **kwargs: object):
        if name == "watchfiles":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    class ImmediateThread:
        def __init__(self, target, daemon: bool) -> None:
            self.target = target

        def start(self) -> None:
            self.target()

    monkeypatch.setattr("builtins.__import__", fake_import)
    monkeypatch.setattr("fluxlit.runtime.reload_watcher.threading.Thread", ImmediateThread)
    _start_streamlit_reload_watcher(lambda: None, debounce_s=0.1, stop_flag=lambda: False)
    assert "requires the `watchfiles` package" in capsys.readouterr().err


def test_reload_watcher_returns_when_stop_flag_set(monkeypatch: pytest.MonkeyPatch) -> None:
    from fluxlit.runtime.reload_watcher import _start_streamlit_reload_watcher

    def fake_watch(*args: object, **kwargs: object):
        yield frozenset()

    class ImmediateThread:
        def __init__(self, target, daemon: bool) -> None:
            self.target = target

        def start(self) -> None:
            self.target()

    calls: list[int] = []
    monkeypatch.setitem(sys.modules, "watchfiles", types.SimpleNamespace(watch=fake_watch))
    monkeypatch.setattr("fluxlit.runtime.reload_watcher.threading.Thread", ImmediateThread)
    _start_streamlit_reload_watcher(
        lambda: calls.append(1), debounce_s=0.01, stop_flag=lambda: True
    )
    assert calls == []


def test_reload_watcher_reports_callback_and_watch_errors(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    from fluxlit.runtime.reload_watcher import _start_streamlit_reload_watcher

    calls = {"n": 0}

    def fake_watch(*args: object, **kwargs: object):
        yield frozenset()
        raise RuntimeError("watch died")

    def on_change() -> None:
        calls["n"] += 1
        raise RuntimeError("reload boom")

    class ImmediateThread:
        def __init__(self, target, daemon: bool) -> None:
            self.target = target

        def start(self) -> None:
            self.target()

    watchfiles = types.SimpleNamespace(watch=fake_watch)
    monkeypatch.setitem(sys.modules, "watchfiles", watchfiles)
    monkeypatch.setattr("fluxlit.runtime.reload_watcher.threading.Thread", ImmediateThread)
    _start_streamlit_reload_watcher(on_change, debounce_s=0.01, stop_flag=lambda: False)
    err = capsys.readouterr().err
    assert "reload failed: reload boom" in err
    assert "file watch exited: watch died" in err
