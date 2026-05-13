"""WebSocket reverse proxy from ASGI to Streamlit upstream."""

from __future__ import annotations

from typing import Any, cast

import anyio
import websockets
from starlette.types import Receive, Scope, Send

from fluxlit.gateway._log import gateway_log
from fluxlit.gateway.options import GatewayProxyOptions
from fluxlit.gateway.upstream_http import (
    forwarded_upstream_header_pairs,
    parse_ws_target,
    public_host_from_scope,
)


async def proxy_websocket(
    scope: Scope,
    receive: Receive,
    send: Send,
    upstream: str,
    streamlit_path: str,
    *,
    forwarded_prefix: str | None = None,
    request_id: str,
    proxy_options: GatewayProxyOptions,
) -> None:
    first = await receive()
    if first["type"] != "websocket.connect":
        await send({"type": "websocket.close", "code": 1002})
        return

    target = parse_ws_target(scope, upstream, path=streamlit_path)
    headers = scope.get("headers") or []
    public_host = public_host_from_scope(scope, upstream)
    extra: list[tuple[str, str]] = [("Host", public_host)]
    extra.extend(
        forwarded_upstream_header_pairs(scope, public_host, forwarded_prefix=forwarded_prefix)
    )
    skip_ws = {
        "host",
        "connection",
        "upgrade",
        "sec-websocket-key",
        "sec-websocket-version",
        # Negotiate extensions only on this hop. Forwarding the browser's
        # Sec-WebSocket-Extensions while this client also adds permessage-deflate breaks
        # the upstream handshake (endless "Connecting" / WS 403). Streamlit's
        # Sec-WebSocket-Protocol line (XSRF + session) is forwarded as-is from the client.
        "sec-websocket-extensions",
        "x-forwarded-for",
        "x-forwarded-host",
        "x-forwarded-proto",
        "x-forwarded-port",
        "x-request-id",
    }
    for k, v in headers:
        key = k.decode("latin-1")
        lk = key.lower()
        if lk in skip_ws:
            continue
        extra.append((key, v.decode("latin-1")))
    extra.append(("X-Request-ID", request_id))

    ws_connect_kw: dict[str, Any] = {"open_timeout": proxy_options.ws_open_timeout_s}
    if proxy_options.ws_max_message_bytes is not None:
        ws_connect_kw["max_size"] = proxy_options.ws_max_message_bytes
    if proxy_options.ws_ping_interval_s is not None:
        ws_connect_kw["ping_interval"] = proxy_options.ws_ping_interval_s
    if proxy_options.ws_ping_timeout_s is not None:
        ws_connect_kw["ping_timeout"] = proxy_options.ws_ping_timeout_s
    if proxy_options.ws_close_timeout_s is not None:
        ws_connect_kw["close_timeout"] = proxy_options.ws_close_timeout_s

    try:
        # Streamlit responds with ``Sec-WebSocket-Protocol: streamlit``. The ``websockets``
        # client requires ``subprotocols=[...]`` whenever the server picks a subprotocol;
        # we still merge *additional_headers* after building the request, so the browser's
        # full ``streamlit, <xsrf>, <session>`` line is sent on the wire.
        async with websockets.connect(
            target,
            additional_headers=extra,
            subprotocols=cast(Any, ["streamlit"]),
            **ws_connect_kw,
        ) as upstream_ws:
            subprotocols = scope.get("subprotocols") or []
            accepted = upstream_ws.subprotocol
            if accepted and accepted in subprotocols:
                await send({"type": "websocket.accept", "subprotocol": accepted})
            else:
                await send({"type": "websocket.accept"})

            relay_close_sent = False

            async def _try_close_client_after_relay_error() -> None:
                """Best-effort server close after the relay hits a non-protocol error."""
                nonlocal relay_close_sent
                if relay_close_sent:
                    return
                relay_close_sent = True
                try:
                    await send({"type": "websocket.close", "code": 1011})
                except Exception as close_exc:
                    gateway_log.debug(
                        "gateway websocket: could not send client close after relay error "
                        "request_id=%s: %s",
                        request_id,
                        close_exc,
                    )

            async with anyio.create_task_group() as tg:

                async def client_to_upstream() -> None:
                    try:
                        while True:
                            message = await receive()
                            mtype = message["type"]
                            if mtype == "websocket.receive":
                                if message.get("bytes") is not None:
                                    await upstream_ws.send(message["bytes"])
                                elif message.get("text") is not None:
                                    await upstream_ws.send(message["text"])
                            elif mtype == "websocket.disconnect":
                                with anyio.move_on_after(0.1):
                                    await upstream_ws.close()
                                tg.cancel_scope.cancel()
                                return
                    except websockets.ConnectionClosed:
                        tg.cancel_scope.cancel()
                    except Exception as exc:
                        gateway_log.warning(
                            "gateway websocket client_to_upstream failed request_id=%s: %s",
                            request_id,
                            exc,
                        )
                        await _try_close_client_after_relay_error()
                        tg.cancel_scope.cancel()

                async def upstream_to_client() -> None:
                    try:
                        while True:
                            msg = await upstream_ws.recv()
                            if isinstance(msg, bytes):
                                await send({"type": "websocket.send", "bytes": msg})
                            else:
                                await send({"type": "websocket.send", "text": msg})
                    except websockets.ConnectionClosed:
                        tg.cancel_scope.cancel()
                    except Exception as exc:
                        gateway_log.warning(
                            "gateway websocket upstream_to_client failed request_id=%s: %s",
                            request_id,
                            exc,
                        )
                        await _try_close_client_after_relay_error()
                        tg.cancel_scope.cancel()

                tg.start_soon(client_to_upstream)
                tg.start_soon(upstream_to_client)
    except (
        OSError,
        TimeoutError,
        websockets.InvalidURI,
        websockets.InvalidHandshake,
        websockets.NegotiationError,
    ) as exc:
        gateway_log.warning("gateway websocket upstream failed: %s", exc)
        await send({"type": "websocket.close", "code": 1011})
