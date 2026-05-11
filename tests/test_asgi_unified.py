"""Production-oriented ASGI tests for the unified FluxLit stack (gateway + Streamlit).

Uses ``httpx.ASGITransport`` for HTTP, ``starlette.testclient.TestClient``, and an explicit
lifespan task (``httpx`` 0.28 ``ASGITransport`` has no ``lifespan=`` kwarg here).
"""

from __future__ import annotations

import asyncio
import importlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from starlette.testclient import TestClient

from fluxlit.asgi_types import ASGIApp, ASGIMessage, Scope
from fluxlit.runtime import asgi_from_fluxlit, create_unified_app, load_fluxlit


@asynccontextmanager
async def _lifespan_running(asgi_app: ASGIApp) -> AsyncIterator[ASGIApp]:
    """Run ASGI lifespan in a background task; yield the same app for concurrent HTTP."""
    q_in: asyncio.Queue[ASGIMessage] = asyncio.Queue()
    q_out: asyncio.Queue[ASGIMessage] = asyncio.Queue()

    async def receive() -> ASGIMessage:
        return await q_in.get()

    async def send(message: ASGIMessage) -> None:
        await q_out.put(message)

    scope: Scope = {  # type: ignore[assignment]
        "type": "lifespan",
        "asgi": {"version": "3.0", "spec_version": "2.0"},
        "state": {},
    }

    async def _run_lifespan() -> None:
        await asgi_app(scope, receive, send)

    task = asyncio.create_task(_run_lifespan())
    await q_in.put({"type": "lifespan.startup"})
    msg = await asyncio.wait_for(q_out.get(), timeout=30.0)
    if msg.get("type") == "lifespan.startup.failed":
        await asyncio.wait_for(task, timeout=30.0)
        pytest.fail(f"lifespan startup failed: {msg.get('message', '')}")
    assert msg["type"] == "lifespan.startup.complete", msg
    try:
        yield asgi_app
    finally:
        await q_in.put({"type": "lifespan.shutdown"})
        msg2 = await asyncio.wait_for(q_out.get(), timeout=30.0)
        assert msg2["type"] == "lifespan.shutdown.complete", msg2
        await asyncio.wait_for(task, timeout=30.0)


async def _httpx_get(asgi_app: ASGIApp, path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=asgi_app, raise_app_exceptions=True)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


def _minimal_asgi_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("fluxlit.runtime._wait_for_tcp", lambda *a, **k: None)
    monkeypatch.setenv("FLUXLIT_APP", "tests.e2e.minimal_app:app")
    monkeypatch.setenv("FLUXLIT_GATEWAY_PORT", "8000")

    class _DummyProc:
        def send_signal(self, _sig: object) -> None:
            return

        def wait(self, timeout: float | None = None) -> int:  # noqa: ARG002
            return 0

        def poll(self) -> int | None:
            return None

        def terminate(self) -> None:
            return

        def kill(self) -> None:
            return

    monkeypatch.setattr(
        "fluxlit.runtime.subprocess.Popen",
        lambda *_a, **_kw: _DummyProc(),
    )


@pytest.mark.asyncio
async def test_httpx_asgi_transport_api_healthz_after_lifespan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HTTP to the API prefix after lifespan startup (concurrent lifespan + HTTP)."""
    _minimal_asgi_env(monkeypatch)
    asgi = create_unified_app()
    async with _lifespan_running(asgi):
        r = await _httpx_get(asgi, "/api/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_httpx_asgi_transport_openapi_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenAPI is mounted under the API prefix."""
    _minimal_asgi_env(monkeypatch)
    asgi = create_unified_app()
    async with _lifespan_running(asgi):
        r = await _httpx_get(asgi, "/api/openapi.json")
    assert r.status_code == 200
    body = r.json()
    assert "openapi" in body
    assert "paths" in body


@pytest.mark.asyncio
async def test_httpx_root_docs_redirects_to_api_docs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gateway redirects ``/docs`` to ``/api/docs`` (browser-friendly)."""
    _minimal_asgi_env(monkeypatch)
    asgi = create_unified_app()
    transport = httpx.ASGITransport(app=asgi, raise_app_exceptions=True)
    async with _lifespan_running(asgi):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/docs", follow_redirects=False)
    assert r.status_code in (301, 302, 303, 307, 308)
    loc = r.headers.get("location", "")
    assert "/api/docs" in loc


def test_starlette_testclient_sync_healthz(monkeypatch: pytest.MonkeyPatch) -> None:
    """Synchronous ``TestClient`` is common in CI and must work with the unified app."""
    _minimal_asgi_env(monkeypatch)
    asgi = create_unified_app()
    with TestClient(asgi, raise_server_exceptions=False) as client:
        r = client.get("/api/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_lifespan_scope_includes_asgi_version_and_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Outer lifespan normalizes ``asgi`` and ``state`` for the inner FastAPI app."""
    _minimal_asgi_env(monkeypatch)
    captured: dict[str, Any] = {}

    fl = load_fluxlit("tests.e2e.minimal_app:app")
    inner = fl.api

    async def spy(scope: Any, receive: Any, send: Any) -> None:
        if scope.get("type") == "lifespan":
            captured["lifespan_scope_keys"] = set(scope.keys())
            captured["asgi"] = dict(scope.get("asgi") or {})
            captured["state"] = scope.get("state")
        await inner(scope, receive, send)

    object.__setattr__(fl, "api", spy)
    asgi = asgi_from_fluxlit(fl, "tests.e2e.minimal_app:app")
    q: list[ASGIMessage] = [{"type": "lifespan.startup"}, {"type": "lifespan.shutdown"}]
    sent: list[ASGIMessage] = []

    async def receive() -> ASGIMessage:
        return q.pop(0)

    async def send(message: ASGIMessage) -> None:
        sent.append(message)

    await asgi({"type": "lifespan"}, receive, send)
    assert captured.get("asgi", {}).get("version") == "3.0"
    assert captured.get("asgi", {}).get("spec_version") == "2.0"
    assert isinstance(captured.get("state"), dict)
    assert "type" in captured.get("lifespan_scope_keys", set())


@pytest.mark.asyncio
async def test_double_lifespan_startup_sends_two_completes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Idempotent second ``lifespan.startup`` must not crash (Uvicorn edge cases)."""
    _minimal_asgi_env(monkeypatch)
    asgi = create_unified_app()
    q: list[ASGIMessage] = [
        {"type": "lifespan.startup"},
        {"type": "lifespan.startup"},
        {"type": "lifespan.shutdown"},
    ]
    sent: list[str] = []

    async def receive() -> ASGIMessage:
        return q.pop(0)

    async def send(message: ASGIMessage) -> None:
        sent.append(str(message.get("type")))

    await asgi({"type": "lifespan"}, receive, send)
    assert sent.count("lifespan.startup.complete") == 2
    assert "lifespan.shutdown.complete" in sent


@pytest.mark.asyncio
async def test_shutdown_without_startup_sends_shutdown_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shutdown alone must complete cleanly (no inner task, no sidecar)."""
    _minimal_asgi_env(monkeypatch)
    asgi = create_unified_app()
    q: list[ASGIMessage] = [{"type": "lifespan.shutdown"}]
    sent: list[ASGIMessage] = []

    async def receive() -> ASGIMessage:
        return q.pop(0)

    async def send(message: ASGIMessage) -> None:
        sent.append(message)

    await asgi({"type": "lifespan"}, receive, send)
    assert any(m.get("type") == "lifespan.shutdown.complete" for m in sent)


@pytest.mark.asyncio
async def test_inner_lifespan_startup_failure_emits_startup_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If FastAPI lifespan fails on startup, server sees ``lifespan.startup.failed``."""
    bad = tmp_path / "bad_lifespan_app.py"
    bad.write_text(
        "from contextlib import asynccontextmanager\n"
        "from fastapi import FastAPI\n"
        "from fluxlit import FluxLit\n"
        "@asynccontextmanager\n"
        "async def lifespan(app: FastAPI):\n"
        "    raise RuntimeError('startup boom')\n"
        "    yield  # pragma: no cover\n"
        "app = FluxLit(title='x', fastapi_kwargs={'lifespan': lifespan})\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("fluxlit.runtime._wait_for_tcp", lambda *a, **k: None)

    class _P:
        def send_signal(self, _s: object) -> None:
            return

        def wait(self, timeout: float | None = None) -> int:  # noqa: ARG002
            return 0

        def poll(self) -> int | None:
            return None

        def terminate(self) -> None:
            return

        def kill(self) -> None:
            return

    monkeypatch.setattr("fluxlit.runtime.subprocess.Popen", lambda *_a, **_kw: _P())
    monkeypatch.setenv("FLUXLIT_APP", "bad_lifespan_app:app")
    monkeypatch.setenv("FLUXLIT_GATEWAY_PORT", "8000")

    asgi = create_unified_app()
    q: list[ASGIMessage] = [{"type": "lifespan.startup"}]
    sent: list[ASGIMessage] = []

    async def receive() -> ASGIMessage:
        return q.pop(0)

    async def send(message: ASGIMessage) -> None:
        sent.append(message)

    await asgi({"type": "lifespan"}, receive, send)
    failed = [m for m in sent if m.get("type") == "lifespan.startup.failed"]
    assert failed, "expected lifespan.startup.failed"
    assert "boom" in (failed[0].get("message") or "")


@pytest.mark.asyncio
async def test_inner_lifespan_shutdown_failure_emits_shutdown_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If FastAPI lifespan fails on shutdown, ASGI server sees ``lifespan.shutdown.failed``."""
    bad = tmp_path / "bad_shutdown_lifespan_app.py"
    bad.write_text(
        "from contextlib import asynccontextmanager\n"
        "from fastapi import FastAPI\n"
        "from fluxlit import FluxLit\n"
        "@asynccontextmanager\n"
        "async def lifespan(app: FastAPI):\n"
        "    yield\n"
        "    raise RuntimeError('shutdown boom')\n"
        "app = FluxLit(title='x', fastapi_kwargs={'lifespan': lifespan})\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("fluxlit.runtime._wait_for_tcp", lambda *a, **k: None)

    class _P:
        def send_signal(self, _s: object) -> None:
            return

        def wait(self, timeout: float | None = None) -> int:  # noqa: ARG002
            return 0

        def poll(self) -> int | None:
            return None

        def terminate(self) -> None:
            return

        def kill(self) -> None:
            return

    monkeypatch.setattr("fluxlit.runtime.subprocess.Popen", lambda *_a, **_kw: _P())
    monkeypatch.setenv("FLUXLIT_APP", "bad_shutdown_lifespan_app:app")
    monkeypatch.setenv("FLUXLIT_GATEWAY_PORT", "8000")

    asgi = create_unified_app()
    q: list[ASGIMessage] = [
        {"type": "lifespan.startup"},
        {"type": "lifespan.shutdown"},
    ]
    sent: list[ASGIMessage] = []

    async def receive() -> ASGIMessage:
        return q.pop(0)

    async def send(message: ASGIMessage) -> None:
        sent.append(message)

    with pytest.raises(RuntimeError, match="shutdown boom"):
        await asgi({"type": "lifespan"}, receive, send)
    failed = [m for m in sent if m.get("type") == "lifespan.shutdown.failed"]
    assert failed, "expected lifespan.shutdown.failed before inner re-raises"
    assert "boom" in (failed[0].get("message") or "")


@pytest.mark.asyncio
async def test_websocket_before_sidecar_sends_close_with_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pre-handshake close must include code (and reason per ASGI HTTP+WS spec)."""
    monkeypatch.setenv("FLUXLIT_APP", "tests.e2e.minimal_app:app")
    asgi = create_unified_app()
    sent: list[ASGIMessage] = []

    async def receive() -> ASGIMessage:
        return {"type": "websocket.connect"}

    async def send(message: ASGIMessage) -> None:
        sent.append(message)

    scope: dict[str, Any] = {
        "type": "websocket",
        "path": "/",
        "headers": [],
        "query_string": b"",
        "subprotocols": [],
        "client": ("127.0.0.1", 12345),
        "server": ("127.0.0.1", 8000),
    }
    await asgi(scope, receive, send)  # type: ignore[arg-type]
    close = next(m for m in sent if m.get("type") == "websocket.close")
    assert close.get("code") == 1013
    assert isinstance(close.get("reason", ""), str)


@pytest.mark.asyncio
async def test_http_503_body_shape_matches_asgi_http_spec(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """503 responses must end the body with ``more_body: False``."""
    monkeypatch.setenv("FLUXLIT_APP", "tests.e2e.minimal_app:app")
    asgi = create_unified_app()
    sent: list[ASGIMessage] = []

    async def receive() -> ASGIMessage:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: ASGIMessage) -> None:
        sent.append(message)

    scope: dict[str, Any] = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [],
        "root_path": "",
        "scheme": "http",
        "client": ("127.0.0.1", 1),
        "server": ("127.0.0.1", 8000),
    }
    await asgi(scope, receive, send)  # type: ignore[arg-type]
    start = next(m for m in sent if m.get("type") == "http.response.start")
    assert start["status"] == 503
    hdrs = cast(list[tuple[bytes, bytes]], list(start.get("headers") or []))
    assert all(isinstance(a, (bytes, bytearray)) for a, _ in hdrs)
    body = next(m for m in sent if m.get("type") == "http.response.body")
    assert body.get("more_body") is False
    assert isinstance(body.get("body"), (bytes, bytearray))


@pytest.mark.asyncio
async def test_sidecar_exit_causes_503_on_subsequent_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If ``poll()`` shows the Streamlit process exited, the next HTTP request returns 503."""
    monkeypatch.setattr("fluxlit.runtime._wait_for_tcp", lambda *a, **k: None)
    monkeypatch.setenv("FLUXLIT_APP", "tests.e2e.minimal_app:app")
    monkeypatch.setenv("FLUXLIT_GATEWAY_PORT", "8000")

    class _Proc:
        _n = 0

        def send_signal(self, _s: object) -> None:
            return

        def wait(self, timeout: float | None = None) -> int:  # noqa: ARG002
            return 0

        def poll(self) -> int | None:
            self._n += 1
            return 1 if self._n >= 2 else None

        def terminate(self) -> None:
            return

        def kill(self) -> None:
            return

    monkeypatch.setattr("fluxlit.runtime.subprocess.Popen", lambda *_a, **_kw: _Proc())
    asgi = create_unified_app()
    async with _lifespan_running(asgi):
        transport = httpx.ASGITransport(app=asgi, raise_app_exceptions=True)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            r1 = await client.get("/api/healthz")
            r2 = await client.get("/api/healthz")
    assert r1.status_code == 200
    assert r2.status_code == 503


@pytest.mark.asyncio
async def test_api_post_chunked_request_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ASGI HTTP must accept multiple ``http.request`` chunks (streaming body)."""
    mod = tmp_path / "echo_chunk_app.py"
    mod.write_text(
        "from starlette.requests import Request\n"
        "from fluxlit import FluxLit\n"
        "app = FluxLit(title='echo')\n"
        "@app.api.post('/echo-len', include_in_schema=False)\n"
        "async def echo_len(request: Request) -> dict[str, int]:\n"
        "    return {'len': len(await request.body())}\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)
    _minimal_asgi_env(monkeypatch)

    echo_chunk_app = importlib.import_module("echo_chunk_app")

    asgi = asgi_from_fluxlit(echo_chunk_app.app, "echo_chunk_app:app")
    chunks = [b"hel", b"lo"]
    idx = {"i": 0}
    sent: list[ASGIMessage] = []

    async def receive() -> ASGIMessage:
        i = idx["i"]
        if i < len(chunks):
            idx["i"] += 1
            more = i < len(chunks) - 1
            return {"type": "http.request", "body": chunks[i], "more_body": more}
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: ASGIMessage) -> None:
        sent.append(message)

    scope: dict[str, Any] = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "path": "/api/echo-len",
        "raw_path": b"/api/echo-len",
        "query_string": b"",
        "headers": [(b"content-type", b"application/octet-stream")],
        "root_path": "",
        "scheme": "http",
        "client": ("127.0.0.1", 1),
        "server": ("127.0.0.1", 8000),
    }
    async with _lifespan_running(asgi):
        await asgi(scope, receive, send)  # type: ignore[arg-type]
    parts = [m for m in sent if m.get("type") == "http.response.body"]
    joined = b"".join(bytes(m.get("body") or b"") for m in parts)
    assert b'"len":5' in joined or b'"len": 5' in joined


@pytest.mark.asyncio
async def test_serial_healthz_burst_after_lifespan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Many sequential health checks succeed (chaos-style micro-stress on API path)."""
    _minimal_asgi_env(monkeypatch)
    asgi = create_unified_app()
    async with _lifespan_running(asgi):
        transport = httpx.ASGITransport(app=asgi, raise_app_exceptions=True)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            for _ in range(100):
                r = await client.get("/api/healthz")
                assert r.status_code == 200
                assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_concurrent_http_requests_after_lifespan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Multiple parallel GETs to the API must all succeed (no global request corruption)."""
    _minimal_asgi_env(monkeypatch)
    asgi = create_unified_app()
    async with _lifespan_running(asgi):
        transport = httpx.ASGITransport(app=asgi, raise_app_exceptions=True)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            results = await asyncio.gather(
                *[client.get("/api/healthz") for _ in range(20)],
            )
    assert all(r.status_code == 200 for r in results)
    assert all(r.json() == {"status": "ok"} for r in results)


@pytest.mark.asyncio
async def test_fluxlit_asgi_custom_route_via_httpx(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Custom FastAPI routes are reachable through the unified ASGI surface."""
    mod = tmp_path / "asgi_ping_mod.py"
    mod.write_text(
        "from fluxlit import FluxLit\n"
        "app = FluxLit(title='p')\n"
        "@app.api.get('/ping-asgi', include_in_schema=False)\n"
        "def _ping() -> dict[str, str]:\n"
        "    return {'pong': 'yes'}\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)
    _minimal_asgi_env(monkeypatch)
    monkeypatch.setenv("FLUXLIT_APP", "asgi_ping_mod:app")

    asgi_ping_mod = importlib.import_module("asgi_ping_mod")

    fl = asgi_ping_mod.app
    asgi = asgi_from_fluxlit(fl, "asgi_ping_mod:app")
    async with _lifespan_running(asgi):
        r = await _httpx_get(asgi, "/api/ping-asgi")
    assert r.status_code == 200
    assert r.json() == {"pong": "yes"}
