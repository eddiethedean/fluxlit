"""Detect Uvicorn multi-process mode incompatible with the unified FluxLit stack."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fluxlit.runtime.env_parse import truthy_env

_log = logging.getLogger("fluxlit.runtime")


def unified_multiworker_startup_error() -> str | None:
    """Return a startup failure message when Uvicorn runs with ``workers`` > 1.

    The unified stack starts a Streamlit sidecar per OS process; multiple Uvicorn
    workers each spawn their own sidecar and break session affinity and operator
    expectations. See deployment docs; ``FLUXLIT_ALLOW_UNIFIED_UVICORN_MULTIWORKER``
    skips this guard for advanced scenarios.
    """
    if truthy_env("FLUXLIT_ALLOW_UNIFIED_UVICORN_MULTIWORKER"):
        return None
    workers = uvicorn_workers_from_running_loop()
    if workers is not None and workers > 1:
        return (
            "FluxLit unified runtime is incompatible with Uvicorn --workers > 1 "
            f"(detected workers={workers}). Use a single worker and scale out with "
            "replicas or separate processes. Set FLUXLIT_ALLOW_UNIFIED_UVICORN_MULTIWORKER=1 "
            "only if you accept an unsupported configuration."
        )
    return None


def uvicorn_workers_from_running_loop() -> int | None:
    """Return ``uvicorn.config.Config.workers`` when a ``LifespanOn`` task is visible.

    Uvicorn's reload supervisor and multi-worker supervisor both spawn children via
    ``multiprocessing``; only ``Config.workers > 1`` indicates the multi-worker layout.
    If no ``LifespanOn`` coroutine frame is found (internal API change), returns ``None``
    and the guard does not fire.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return None

    for task in asyncio.all_tasks(loop):
        coro = _task_coro(task)
        if coro is None:
            continue
        frame = getattr(coro, "cr_frame", None)
        if frame is None:
            continue
        self_obj = frame.f_locals.get("self")
        if self_obj is None:
            continue
        cls = type(self_obj)
        mod_ok = getattr(cls, "__module__", "") == "uvicorn.lifespan.on"
        if cls.__qualname__ != "LifespanOn" or not mod_ok:
            continue
        cfg = getattr(self_obj, "config", None)
        if cfg is None:
            continue
        workers = getattr(cfg, "workers", None)
        if workers is None:
            continue
        try:
            return int(workers)
        except (TypeError, ValueError):
            _log.debug("Ignoring non-int uvicorn Config.workers=%r", workers)
            return None
    return None


def _task_coro(task: asyncio.Task[Any]) -> Any:
    get_coro = getattr(task, "get_coro", None)
    if callable(get_coro):
        return get_coro()
    return getattr(task, "_coro", None)
