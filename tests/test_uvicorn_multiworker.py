"""Tests for Uvicorn multi-worker detection on the unified FluxLit stack."""

from __future__ import annotations

import asyncio
import logging
import types
from unittest.mock import MagicMock

import pytest
from uvicorn.lifespan.on import LifespanOn


@pytest.mark.asyncio
async def test_uvicorn_workers_from_running_loop_reads_lifespan_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fluxlit.runtime import uvicorn_multiworker

    lo = LifespanOn.__new__(LifespanOn)
    lo.config = types.SimpleNamespace(workers=4)

    mock_coro = MagicMock()
    mock_coro.cr_frame = types.SimpleNamespace(f_locals={"self": lo})
    mock_task = MagicMock()
    mock_task.get_coro.return_value = mock_coro

    monkeypatch.setattr(asyncio, "all_tasks", lambda loop=None: {mock_task})

    assert uvicorn_multiworker.uvicorn_workers_from_running_loop() == 4


@pytest.mark.asyncio
async def test_uvicorn_workers_from_running_loop_ignores_wrong_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fluxlit.runtime import uvicorn_multiworker

    class NotLifespan:
        config = types.SimpleNamespace(workers=9)

    mock_coro = MagicMock()
    mock_coro.cr_frame = types.SimpleNamespace(f_locals={"self": NotLifespan()})
    mock_task = MagicMock()
    mock_task.get_coro.return_value = mock_coro

    monkeypatch.setattr(asyncio, "all_tasks", lambda loop=None: {mock_task})

    assert uvicorn_multiworker.uvicorn_workers_from_running_loop() is None


def test_unified_multiworker_startup_error_when_workers_gt_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fluxlit.runtime import uvicorn_multiworker

    monkeypatch.delenv("FLUXLIT_ALLOW_UNIFIED_UVICORN_MULTIWORKER", raising=False)
    monkeypatch.setattr(
        uvicorn_multiworker,
        "uvicorn_workers_from_running_loop",
        lambda: 3,
    )
    err = uvicorn_multiworker.unified_multiworker_startup_error()
    assert err is not None
    assert "workers=3" in err
    assert "FLUXLIT_ALLOW_UNIFIED_UVICORN_MULTIWORKER" in err


def test_unified_multiworker_startup_error_respects_allow_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fluxlit.runtime import uvicorn_multiworker

    monkeypatch.setenv("FLUXLIT_ALLOW_UNIFIED_UVICORN_MULTIWORKER", "1")
    monkeypatch.setattr(
        uvicorn_multiworker,
        "uvicorn_workers_from_running_loop",
        lambda: 99,
    )
    assert uvicorn_multiworker.unified_multiworker_startup_error() is None


def test_uvicorn_workers_from_running_loop_without_event_loop() -> None:
    from fluxlit.runtime import uvicorn_multiworker

    assert uvicorn_multiworker.uvicorn_workers_from_running_loop() is None


@pytest.mark.asyncio
async def test_uvicorn_workers_skips_task_when_coro_is_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fluxlit.runtime import uvicorn_multiworker

    mock_task = MagicMock()
    mock_task.get_coro.return_value = None
    monkeypatch.setattr(asyncio, "all_tasks", lambda loop=None: {mock_task})

    assert uvicorn_multiworker.uvicorn_workers_from_running_loop() is None


@pytest.mark.asyncio
async def test_uvicorn_workers_skips_when_cr_frame_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fluxlit.runtime import uvicorn_multiworker

    mock_coro = MagicMock(cr_frame=None)
    mock_task = MagicMock()
    mock_task.get_coro.return_value = mock_coro
    monkeypatch.setattr(asyncio, "all_tasks", lambda loop=None: {mock_task})

    assert uvicorn_multiworker.uvicorn_workers_from_running_loop() is None


@pytest.mark.asyncio
async def test_uvicorn_workers_skips_when_frame_has_no_self(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fluxlit.runtime import uvicorn_multiworker

    mock_coro = MagicMock()
    mock_coro.cr_frame = types.SimpleNamespace(f_locals={})
    mock_task = MagicMock()
    mock_task.get_coro.return_value = mock_coro
    monkeypatch.setattr(asyncio, "all_tasks", lambda loop=None: {mock_task})

    assert uvicorn_multiworker.uvicorn_workers_from_running_loop() is None


@pytest.mark.asyncio
async def test_uvicorn_workers_skips_when_config_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fluxlit.runtime import uvicorn_multiworker

    lo = LifespanOn.__new__(LifespanOn)
    mock_coro = MagicMock()
    mock_coro.cr_frame = types.SimpleNamespace(f_locals={"self": lo})
    mock_task = MagicMock()
    mock_task.get_coro.return_value = mock_coro
    monkeypatch.setattr(asyncio, "all_tasks", lambda loop=None: {mock_task})

    assert uvicorn_multiworker.uvicorn_workers_from_running_loop() is None


@pytest.mark.asyncio
async def test_uvicorn_workers_skips_when_workers_attr_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fluxlit.runtime import uvicorn_multiworker

    lo = LifespanOn.__new__(LifespanOn)
    lo.config = types.SimpleNamespace(workers=None)
    mock_coro = MagicMock()
    mock_coro.cr_frame = types.SimpleNamespace(f_locals={"self": lo})
    mock_task = MagicMock()
    mock_task.get_coro.return_value = mock_coro
    monkeypatch.setattr(asyncio, "all_tasks", lambda loop=None: {mock_task})

    assert uvicorn_multiworker.uvicorn_workers_from_running_loop() is None


@pytest.mark.asyncio
async def test_uvicorn_workers_invalid_workers_logs_debug(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from fluxlit.runtime import uvicorn_multiworker

    lo = LifespanOn.__new__(LifespanOn)
    lo.config = types.SimpleNamespace(workers="not-an-int")
    mock_coro = MagicMock()
    mock_coro.cr_frame = types.SimpleNamespace(f_locals={"self": lo})
    mock_task = MagicMock()
    mock_task.get_coro.return_value = mock_coro
    monkeypatch.setattr(asyncio, "all_tasks", lambda loop=None: {mock_task})

    caplog.set_level(logging.DEBUG, logger="fluxlit.runtime")
    assert uvicorn_multiworker.uvicorn_workers_from_running_loop() is None
    assert any("Ignoring non-int uvicorn Config.workers" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_task_coro_falls_back_to_private_coro_attr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fluxlit.runtime import uvicorn_multiworker

    lo = LifespanOn.__new__(LifespanOn)
    lo.config = types.SimpleNamespace(workers=2)
    mock_coro = MagicMock()
    mock_coro.cr_frame = types.SimpleNamespace(f_locals={"self": lo})
    mock_task = types.SimpleNamespace(_coro=mock_coro)

    monkeypatch.setattr(asyncio, "all_tasks", lambda loop=None: [mock_task])

    assert uvicorn_multiworker.uvicorn_workers_from_running_loop() == 2


@pytest.mark.asyncio
async def test_lifespan_bridge_multiworker_guard_fails_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fluxlit import FluxLit
    from fluxlit.runtime.lifespan_bridge import build_unified_fluxlit_asgi_app

    async def gateway(scope: object, receive: object, send: object) -> None:
        return None

    monkeypatch.setattr(
        "fluxlit.runtime.lifespan_bridge.unified_multiworker_startup_error",
        lambda: "multi-worker forbidden (test)",
    )

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
        return {"type": "lifespan.startup"}

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    await app({"type": "lifespan"}, receive, send)
    assert sent == [{"type": "lifespan.startup.failed", "message": "multi-worker forbidden (test)"}]
