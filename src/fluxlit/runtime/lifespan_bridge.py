"""Unified ASGI lifespan: Streamlit sidecar + inner FastAPI lifespan queue bridge."""

from __future__ import annotations

import asyncio
import subprocess
import sys
from collections.abc import Awaitable, Callable, Mapping
from typing import TYPE_CHECKING, Any, TypeAlias, cast

from starlette.types import ASGIApp, Receive, Scope, Send

from fluxlit.asgi_types import ASGIMessage
from fluxlit.runtime.constants import _STREAMLIT_TCP_WAIT_S
from fluxlit.runtime.streamlit_proc import _StreamlitPopenKwargs, _terminate_process
from fluxlit.runtime.uvicorn_multiworker import unified_multiworker_startup_error
from fluxlit.runtime.wait_tcp import _invoke_wait_for_tcp

if TYPE_CHECKING:
    from fluxlit.app import FluxLit

    FluxLitType: TypeAlias = FluxLit[Any]


def build_unified_fluxlit_asgi_app(
    fl: FluxLitType,
    *,
    gateway_app: ASGIApp,
    cmd: list[str],
    env: Mapping[str, str],
    streamlit_port: int,
    upstream_url_box: list[str],
) -> ASGIApp:
    """Return ASGI app: lifespan starts Streamlit + bridges ``fl.api`` lifespan; HTTP/WS to gateway.

    ``upstream_url_box`` is a single-element list shared with the gateway's
    ``upstream_resolver`` so the proxy sees the sidecar URL as soon as startup completes.
    """
    streamlit_proc: subprocess.Popen[bytes] | None = None

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        nonlocal streamlit_proc

        stype = scope.get("type")
        if stype == "lifespan":
            # Ensure keys required / conventional for ASGI Lifespan and framework routers.
            lifespan_scope: Scope = cast(Scope, dict(scope))
            lifespan_scope.setdefault("state", {})
            asgi_info: dict[str, Any] = dict(lifespan_scope.get("asgi") or {})
            asgi_info.setdefault("version", "3.0")
            asgi_info.setdefault("spec_version", "2.0")
            lifespan_scope["asgi"] = asgi_info

            # ASGI lifespan messages are dynamic dicts; the inner app expects MutableMapping.
            lifespan_queue: asyncio.Queue[ASGIMessage] = asyncio.Queue()
            inner_task: asyncio.Task[None] | None = None

            async def bridge_receive() -> ASGIMessage:
                return await lifespan_queue.get()

            async def bridge_send(message: ASGIMessage) -> None:
                await send(message)

            while True:
                message = dict(await receive())
                msg_type = message.get("type")

                if msg_type == "lifespan.startup":
                    if inner_task is not None:
                        await send({"type": "lifespan.startup.complete"})
                        continue
                    mw_err = unified_multiworker_startup_error()
                    if mw_err:
                        await send({"type": "lifespan.startup.failed", "message": mw_err})
                        return
                    try:
                        popen_kwargs: _StreamlitPopenKwargs = {"env": env}
                        if sys.platform.startswith("win"):
                            popen_kwargs["creationflags"] = getattr(  # noqa: B009
                                subprocess, "CREATE_NEW_PROCESS_GROUP"
                            )
                        else:
                            popen_kwargs["start_new_session"] = True  # pragma: no cover

                        streamlit_proc = subprocess.Popen(cmd, **popen_kwargs)
                        _invoke_wait_for_tcp(
                            "127.0.0.1",
                            streamlit_port,
                            timeout_s=_STREAMLIT_TCP_WAIT_S,
                        )
                        upstream_url_box[0] = f"http://127.0.0.1:{streamlit_port}"
                    except Exception as e:
                        if streamlit_proc is not None:
                            _terminate_process(streamlit_proc, timeout_s=2.0)
                            streamlit_proc = None
                        upstream_url_box[0] = ""
                        await send({"type": "lifespan.startup.failed", "message": str(e)})
                        return

                    inner_task = asyncio.create_task(
                        fl.api(lifespan_scope, bridge_receive, bridge_send)
                    )
                    await lifespan_queue.put(message)
                    await asyncio.sleep(0)
                    if inner_task.done():
                        upstream_url_box[0] = ""
                        if streamlit_proc is not None:
                            _terminate_process(streamlit_proc, timeout_s=2.0)
                            streamlit_proc = None
                        exc = inner_task.exception()
                        if exc is not None:
                            await send({"type": "lifespan.startup.failed", "message": str(exc)})
                        else:
                            await send(
                                {
                                    "type": "lifespan.startup.failed",
                                    "message": ("inner application lifespan exited during startup"),
                                }
                            )
                        return
                    continue

                if msg_type == "lifespan.shutdown":
                    try:
                        if inner_task is not None:
                            await lifespan_queue.put(message)
                            await inner_task
                        else:
                            await send({"type": "lifespan.shutdown.complete"})
                    finally:
                        upstream_url_box[0] = ""
                        if streamlit_proc is not None:
                            _terminate_process(streamlit_proc, timeout_s=5.0)
                            streamlit_proc = None
                        shutdown_hook = cast(
                            Callable[[], Awaitable[None]] | None,
                            getattr(gateway_app, "fluxlit_shutdown", None),
                        )
                        if shutdown_hook is not None:
                            await shutdown_hook()
                    return

                # Lifespan spec: only startup and shutdown are defined for receive.
                continue

        if stype not in {"http", "websocket"}:
            msg = f"Unsupported ASGI scope type: {stype!r}"
            raise RuntimeError(msg)

        # If the sidecar is down (or lifespan wasn't run), fail fast with a clean response.
        u = upstream_url_box[0]
        if not u or (streamlit_proc is not None and streamlit_proc.poll() is not None):
            upstream_url_box[0] = ""
            streamlit_proc = None
            if stype == "http":
                await send(
                    {
                        "type": "http.response.start",
                        "status": 503,
                        "headers": [(b"content-type", b"text/plain; charset=utf-8")],
                    }
                )
                await send(
                    {
                        "type": "http.response.body",
                        "body": b"FluxLit Streamlit sidecar is not running.",
                        "more_body": False,
                    }
                )
                return
            if stype == "websocket":
                await send(
                    {
                        "type": "websocket.close",
                        "code": 1013,
                        "reason": "FluxLit Streamlit sidecar is not running.",
                    }
                )
                return

        await gateway_app(scope, receive, send)

    return app
