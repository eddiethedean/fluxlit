"""WebSocket proxy happy path against a real local echo server (Streamlit-shaped path)."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Generator
from typing import Any

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient
from websockets.asyncio.server import serve

from fluxlit.gateway import build_gateway
from fluxlit.runtime import find_free_port


def _run_echo_server(port: int, ready: threading.Event, stop: threading.Event) -> None:
    async def handler(ws: Any) -> None:
        async for message in ws:
            await ws.send(message)

    async def runner() -> None:
        async with serve(
            handler,
            "127.0.0.1",
            port,
            subprotocols=["streamlit"],
            compression=None,
        ):
            ready.set()
            while not stop.is_set():
                await asyncio.sleep(0.05)

    asyncio.run(runner())


@pytest.fixture
def ws_echo_upstream() -> Generator[str, None, None]:
    port = find_free_port()
    ready = threading.Event()
    stop = threading.Event()
    thread = threading.Thread(
        target=_run_echo_server,
        args=(port, ready, stop),
        daemon=True,
    )
    thread.start()
    assert ready.wait(timeout=15), "WebSocket echo server did not start"
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        stop.set()
        thread.join(timeout=10)


def test_websocket_proxy_echo_root_path(ws_echo_upstream: str) -> None:
    gateway = build_gateway(FastAPI(), ws_echo_upstream, api_prefix="/api")
    with TestClient(gateway) as client:
        with client.websocket_connect(
            "/_stcore/stream",
            subprotocols=["streamlit"],
        ) as ws:
            ws.send_text("ping-echo")
            assert ws.receive_text() == "ping-echo"


def test_websocket_proxy_echo_under_subpath(ws_echo_upstream: str) -> None:
    gateway = build_gateway(
        FastAPI(),
        ws_echo_upstream,
        api_prefix="/api",
        root_mount="/myapp",
    )
    with TestClient(gateway) as client:
        with client.websocket_connect(
            "/myapp/_stcore/stream",
            subprotocols=["streamlit"],
        ) as ws:
            ws.send_text("subpath")
            assert ws.receive_text() == "subpath"


@pytest.mark.slow
def test_websocket_proxy_echo_repeated_sessions(ws_echo_upstream: str) -> None:
    """Many short-lived WebSocket sessions (stability / reconnect-style signal)."""
    gateway = build_gateway(FastAPI(), ws_echo_upstream, api_prefix="/api")
    with TestClient(gateway) as client:
        for i in range(25):
            with client.websocket_connect(
                "/_stcore/stream",
                subprotocols=["streamlit"],
            ) as ws:
                msg = f"burst-{i}"
                ws.send_text(msg)
                assert ws.receive_text() == msg
