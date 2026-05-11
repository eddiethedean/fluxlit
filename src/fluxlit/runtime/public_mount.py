"""ASGI ``root_path`` injection for subpath deployments without Uvicorn doubling."""

from __future__ import annotations

from starlette.types import ASGIApp, Receive, Scope, Send

from fluxlit.gateway import normalize_root_mount


def _inject_public_root_path(app: ASGIApp, public_mount: str) -> ASGIApp:
    """Apply ASGI ``root_path`` without Uvicorn path doubling.

    Uvicorn implements ``Config.root_path`` by prepending it to every request path.
    Reverse proxies that forward the **full** public path (e.g. ``/myapp/api/...``)
    would otherwise yield ``/myapp/myapp/api/...`` in ``scope["path"]``.

    We run Uvicorn with ``root_path=""`` and set the browser-visible mount here when
    the server left ``root_path`` empty, so both **strip-prefix** and **full-path**
    upstream shapes keep correct routing and FastAPI OpenAPI URL generation.
    """
    mount = normalize_root_mount(public_mount)
    if not mount:
        return app

    async def wrapped(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            prior = (scope.get("root_path") or "").strip()
            if not prior:
                scope = dict(scope)
                scope["root_path"] = mount
        await app(scope, receive, send)

    return wrapped
