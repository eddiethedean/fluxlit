"""Small ASGI HTTP/WebSocket response helpers for the gateway."""

from __future__ import annotations

from starlette.types import Receive, Send

_BAD_UPSTREAM_BODY = (
    b"FluxLit: Streamlit upstream URL is missing "
    b"(set FLUXLIT_STREAMLIT_UPSTREAM or fix FLUXLIT_STREAMLIT_UPSTREAM_FILE)."
)


async def not_found(send: Send) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": 404,
            "headers": [(b"content-type", b"text/plain; charset=utf-8")],
        }
    )
    await send({"type": "http.response.body", "body": b"Not Found"})


async def redirect(send: Send, location: str, *, status: int = 307) -> None:
    """Send a redirect; default 307 so the client keeps the same method (GET/HEAD)."""
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"location", location.encode("ascii")),
                (b"content-length", b"0"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": b""})


async def bad_streamlit_upstream_http(send: Send) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": 502,
            "headers": [(b"content-type", b"text/plain; charset=utf-8")],
        }
    )
    await send({"type": "http.response.body", "body": _BAD_UPSTREAM_BODY})


async def bad_streamlit_upstream_ws(receive: Receive, send: Send) -> None:
    """Close the socket when no upstream base URL is available."""
    while True:
        msg = await receive()
        if msg["type"] == "websocket.connect":
            await send(
                {
                    "type": "websocket.close",
                    "code": 1011,
                    "reason": b"Streamlit upstream missing",
                }
            )
            return
        if msg["type"] == "websocket.disconnect":
            return


async def respond_413_payload_too_large(send: Send) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [(b"content-type", b"text/plain; charset=utf-8")],
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": (
                b"Payload Too Large: proxied request body exceeds "
                b"FLUXLIT_GATEWAY_MAX_PROXY_REQUEST_BODY_BYTES"
            ),
            "more_body": False,
        }
    )
