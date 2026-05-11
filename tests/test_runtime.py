from __future__ import annotations

from pathlib import Path

import pytest

from fluxlit import FluxLit
from fluxlit.runtime import (
    _build_streamlit_cmd,
    _build_streamlit_env,
    _inject_public_root_path,
    asgi_from_fluxlit,
    create_unified_app,
    find_free_port,
    internal_api_base_url,
    load_fluxlit,
)


def test_load_fluxlit_rejects_bad_target() -> None:
    with pytest.raises(ValueError):
        load_fluxlit("nocolon")


def test_load_fluxlit_rejects_non_fluxlit() -> None:
    with pytest.raises(TypeError):
        load_fluxlit("json:loads")


def test_load_fluxlit_module_not_found() -> None:
    with pytest.raises(ModuleNotFoundError, match="PYTHONPATH"):
        load_fluxlit("definitely_missing_fluxlit_module_xyz:app")


def test_load_fluxlit_missing_attribute(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = tmp_path / "mod_attr.py"
    mod.write_text("x = 1\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    with pytest.raises(AttributeError):
        load_fluxlit("mod_attr:there_is_no_such_attr")


def test_load_fluxlit_prefers_local_app_py_over_polluted_syspath(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If sys.path includes FluxLit's internal package dir, "import app" can resolve wrong.

    Ensure load_fluxlit("app:app") still loads ./app.py from the working directory when it
    exists.
    """
    app_py = tmp_path / "app.py"
    app_py.write_text(
        "from fluxlit import FluxLit\napp = FluxLit(title='from_local_app_py')\n",
        encoding="utf-8",
    )

    # Simulate the footgun: PYTHONPATH accidentally includes ".../fluxlit/src/fluxlit".
    # That directory contains FluxLit's own app.py, importable as top-level "app".
    repo_fluxlit_pkg_dir = Path(__file__).resolve().parents[1] / "src" / "fluxlit"
    monkeypatch.syspath_prepend(str(repo_fluxlit_pkg_dir))

    monkeypatch.chdir(tmp_path)
    fl = load_fluxlit("app:app")
    assert fl.settings.title == "from_local_app_py"


def test_internal_api_base_url_maps_inaddr_any_to_loopback() -> None:
    assert internal_api_base_url(bind_host="0.0.0.0", port=8000, api_mount_path="/api") == (
        "http://127.0.0.1:8000/api"
    )
    assert internal_api_base_url(bind_host="", port=9000, api_mount_path="/api") == (
        "http://127.0.0.1:9000/api"
    )
    assert internal_api_base_url(bind_host="::", port=8000, api_mount_path="/api") == (
        "http://127.0.0.1:8000/api"
    )


def test_internal_api_base_url_brackets_ipv6() -> None:
    assert internal_api_base_url(bind_host="::1", port=8000, api_mount_path="/api") == (
        "http://[::1]:8000/api"
    )
    assert internal_api_base_url(bind_host="[::1]", port=8000, api_mount_path="/v1") == (
        "http://[::1]:8000/v1"
    )


def test_internal_api_base_url_plain_hostnames() -> None:
    assert internal_api_base_url(bind_host="127.0.0.1", port=1, api_mount_path="/api") == (
        "http://127.0.0.1:1/api"
    )
    assert internal_api_base_url(bind_host="localhost", port=8000, api_mount_path="api") == (
        "http://localhost:8000/api"
    )


def test_find_free_port_returns_ephemeral_port() -> None:
    a = find_free_port()
    b = find_free_port()
    assert 1024 < a < 65536
    assert 1024 < b < 65536
    assert a != b


def test_build_streamlit_env_sets_fluxlit_vars() -> None:
    env = _build_streamlit_env(
        target="m:app",
        api_prefix="/api",
        internal_api_base="http://127.0.0.1:8000/api",
    )
    assert env["FLUXLIT_APP"] == "m:app"
    assert env["FLUXLIT_API_PREFIX"] == "/api"
    assert env["FLUXLIT_INTERNAL_API_BASE"] == "http://127.0.0.1:8000/api"


def test_build_streamlit_cmd_contains_port(tmp_path) -> None:
    runner = tmp_path / "streamlit_main.py"
    cmd = _build_streamlit_cmd(runner=runner, port=1234)
    assert "streamlit" in cmd
    assert "run" in cmd
    assert str(runner) in cmd
    assert "1234" in cmd
    assert "--server.address" in cmd
    assert "127.0.0.1" in cmd
    assert "--server.enableXsrfProtection" in cmd
    assert "--server.enableCORS" in cmd
    assert cmd.count("false") >= 2


def test_build_streamlit_cmd_adds_base_url_path(tmp_path) -> None:
    runner = tmp_path / "streamlit_main.py"
    cmd = _build_streamlit_cmd(runner=runner, port=1234, base_url_path="/connect/app123")
    assert "--server.baseUrlPath" in cmd
    assert cmd[cmd.index("--server.baseUrlPath") + 1] == "/connect/app123"


def test_public_mount_path_prefers_root_path() -> None:
    from fluxlit.config import FluxlitSettings

    s = FluxlitSettings(root_path="/a", streamlit_public_path="/b")
    assert s.public_mount_path() == "/a"


def test_public_mount_path_falls_back_to_streamlit_public() -> None:
    from fluxlit.config import FluxlitSettings

    s = FluxlitSettings(root_path="", streamlit_public_path="/legacy")
    assert s.public_mount_path() == "/legacy"


@pytest.mark.asyncio
async def test_inject_public_root_path_fills_empty_asgi_root_path() -> None:
    """Uvicorn runs with root_path=''; wrapper supplies the browser mount for OpenAPI."""
    captured: dict[str, str] = {}

    async def inner(scope, receive, send):  # noqa: ARG001
        captured["root_path"] = str(scope.get("root_path") or "")

    app = _inject_public_root_path(inner, "/myapp")
    await app({"type": "http", "path": "/api/healthz", "root_path": ""}, None, None)  # type: ignore[arg-type]
    assert captured["root_path"] == "/myapp"


@pytest.mark.asyncio
async def test_inject_public_root_path_noop_when_root_path_already_set() -> None:
    captured: dict[str, str] = {}

    async def inner(scope, receive, send):  # noqa: ARG001
        captured["root_path"] = str(scope.get("root_path") or "")

    app = _inject_public_root_path(inner, "/myapp")
    await app(
        {"type": "http", "path": "/x", "root_path": "/custom"},
        None,
        None,  # type: ignore[arg-type]
    )
    assert captured["root_path"] == "/custom"


@pytest.mark.asyncio
async def test_create_unified_app_starts_and_stops_streamlit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started: dict[str, object] = {}
    stopped: dict[str, bool] = {"ok": False}

    class DummyProc:
        def __init__(self) -> None:
            self.pid = 123
            self._signaled = False

        def send_signal(self, _sig: object) -> None:  # noqa: ARG002
            self._signaled = True
            stopped["ok"] = True

        def wait(self, timeout: float | None = None) -> int:  # noqa: ARG002
            return 0

        def poll(self) -> int | None:
            return None

        def terminate(self) -> None:
            stopped["ok"] = True

        def kill(self) -> None:
            stopped["ok"] = True

    def fake_popen(cmd: list[str], **kwargs: object) -> DummyProc:
        started["cmd"] = cmd
        started["env"] = dict(kwargs.get("env") or {})
        return DummyProc()

    # Don't actually wait on a port.
    monkeypatch.setattr("fluxlit.runtime._wait_for_tcp", lambda *a, **k: None)
    monkeypatch.setattr("fluxlit.runtime.subprocess.Popen", fake_popen)
    monkeypatch.setenv("FLUXLIT_APP", "tests.e2e.minimal_app:app")
    monkeypatch.setenv("FLUXLIT_GATEWAY_PORT", "8000")

    asgi = create_unified_app()

    q: list[dict[str, object]] = [{"type": "lifespan.startup"}, {"type": "lifespan.shutdown"}]
    sent: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        return q.pop(0)

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    await asgi({"type": "lifespan"}, receive, send)
    assert {"type": "lifespan.startup.complete"} in sent
    assert "cmd" in started
    assert "env" in started
    assert started["env"].get("FLUXLIT_APP") == "tests.e2e.minimal_app:app"
    assert {"type": "lifespan.shutdown.complete"} in sent
    assert stopped["ok"] is True


@pytest.mark.asyncio
async def test_create_unified_app_startup_failed_sends_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("nope")

    monkeypatch.setattr("fluxlit.runtime.subprocess.Popen", _boom)
    monkeypatch.setenv("FLUXLIT_APP", "tests.e2e.minimal_app:app")

    asgi = create_unified_app()
    q: list[dict[str, object]] = [{"type": "lifespan.startup"}]
    sent: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        return q.pop(0)

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    await asgi({"type": "lifespan"}, receive, send)
    assert any(m.get("type") == "lifespan.startup.failed" for m in sent)


@pytest.mark.asyncio
async def test_create_unified_app_http_before_startup_is_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FLUXLIT_APP", "tests.e2e.minimal_app:app")
    asgi = create_unified_app()

    sent: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    scope: dict[str, object] = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "root_path": "",
    }
    await asgi(scope, receive, send)  # type: ignore[arg-type]
    start = next(m for m in sent if m.get("type") == "http.response.start")
    assert start["status"] == 503
    body = next(m for m in sent if m.get("type") == "http.response.body")
    assert body.get("more_body") is False


def test_asgi_from_fluxlit_rejects_empty_target() -> None:
    fl = FluxLit(title="t")
    with pytest.raises(ValueError, match="import_target"):
        asgi_from_fluxlit(fl, "  ")


@pytest.mark.asyncio
async def test_fluxlit_instance_is_uvicorn_entrypoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``uvicorn`` can use the FluxLit object directly: ``uvicorn module:app``."""
    started: dict[str, object] = {}

    class DummyProc:
        def send_signal(self, _sig: object) -> None:  # noqa: ARG002
            return

        def wait(self, timeout: float | None = None) -> int:  # noqa: ARG002
            return 0

        def poll(self) -> int | None:
            return None

        def terminate(self) -> None:
            return

        def kill(self) -> None:
            return

    def fake_popen(*_a: object, **_kw: object) -> DummyProc:
        started["ran"] = True
        return DummyProc()

    monkeypatch.setattr("fluxlit.runtime._wait_for_tcp", lambda *a, **k: None)
    monkeypatch.setattr("fluxlit.runtime.subprocess.Popen", fake_popen)
    monkeypatch.setenv("FLUXLIT_APP", "tests.e2e.minimal_app:app")
    monkeypatch.setenv("FLUXLIT_GATEWAY_PORT", "8000")

    fl = load_fluxlit("tests.e2e.minimal_app:app")
    q: list[dict[str, object]] = [{"type": "lifespan.startup"}, {"type": "lifespan.shutdown"}]
    sent: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        return q.pop(0)

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    await fl({"type": "lifespan"}, receive, send)
    assert started.get("ran") is True
    assert {"type": "lifespan.startup.complete"} in sent
    assert {"type": "lifespan.shutdown.complete"} in sent


@pytest.mark.asyncio
async def test_create_unified_app_rejects_unknown_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLUXLIT_APP", "tests.e2e.minimal_app:app")
    asgi = create_unified_app()

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(_message: dict[str, object]) -> None:
        return

    with pytest.raises(RuntimeError, match="Unsupported ASGI scope"):
        await asgi({"type": "ftp"}, receive, send)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_create_unified_app_runs_inner_fastapi_lifespan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Lifespan is bridged to the inner FastAPI app (ASGI lifespan + framework hooks)."""
    hook = tmp_path / "hook_app.py"
    hook.write_text(
        "from contextlib import asynccontextmanager\n"
        "from fastapi import FastAPI\n"
        "from fluxlit import FluxLit\n"
        'STATE = {"v": 0}\n'
        "@asynccontextmanager\n"
        "async def lifespan(app: FastAPI):\n"
        "    STATE['v'] = 1\n"
        "    yield\n"
        "    STATE['v'] = 2\n"
        "app = FluxLit(title='t', fastapi_kwargs={'lifespan': lifespan})\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)

    started: dict[str, object] = {}

    class DummyProc:
        def send_signal(self, _sig: object) -> None:  # noqa: ARG002
            return

        def wait(self, timeout: float | None = None) -> int:  # noqa: ARG002
            return 0

        def poll(self) -> int | None:
            return None

        def terminate(self) -> None:
            return

        def kill(self) -> None:
            return

    monkeypatch.setattr("fluxlit.runtime._wait_for_tcp", lambda *a, **k: None)

    def fake_popen(*_a: object, **_kw: object) -> DummyProc:
        started["ok"] = True
        return DummyProc()

    monkeypatch.setattr("fluxlit.runtime.subprocess.Popen", fake_popen)
    monkeypatch.setenv("FLUXLIT_APP", "hook_app:app")
    monkeypatch.setenv("FLUXLIT_GATEWAY_PORT", "8000")

    import hook_app  # noqa: PLC0415 — loaded after sys.path tweak

    asgi = create_unified_app()
    assert hook_app.STATE["v"] == 0

    q: list[dict[str, object]] = [{"type": "lifespan.startup"}, {"type": "lifespan.shutdown"}]
    sent: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        return q.pop(0)

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    await asgi({"type": "lifespan"}, receive, send)
    assert hook_app.STATE["v"] == 2
    assert {"type": "lifespan.startup.complete"} in sent
    assert {"type": "lifespan.shutdown.complete"} in sent
