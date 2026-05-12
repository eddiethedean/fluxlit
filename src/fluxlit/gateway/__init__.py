"""ASGI gateway: dispatch ``api_prefix`` to FastAPI, proxy everything else to Streamlit.

HTTP requests and WebSockets are forwarded to an upstream base URL (the Streamlit
server). The client's ``Host`` header is preserved on the upstream request so
Streamlit sees the **public** gateway host/port (e.g. ``127.0.0.1:8777``), matching
the browser's ``Origin``; otherwise WebSocket same-origin checks fail and the UI
stays blank/black.

Request IDs are taken from ``X-Request-ID`` or generated, stored in
:mod:`fluxlit.logging` for the duration of each request, and **re-sent to
Streamlit** on proxied HTTP and WebSocket hops as authoritative ``X-Request-ID`` (the
gateway wins over any client-supplied value on that upstream leg).

Top-level ``/docs``, ``/redoc``, and ``/openapi.json`` redirect to the same paths under
``api_prefix`` so Swagger is not accidentally proxied to Streamlit (which would look
like a blank page).
"""

from __future__ import annotations

import httpx  # noqa: F401 — tests monkeypatch ``fluxlit.gateway.httpx.AsyncClient``
import websockets  # noqa: F401 — tests monkeypatch ``fluxlit.gateway.websockets.connect``

from fluxlit.api_mount import normalize_api_mount_path
from fluxlit.gateway.builder import build_gateway
from fluxlit.gateway.header_filter import filter_request_headers as _filter_request_headers
from fluxlit.gateway.http_proxy import _proxy_http
from fluxlit.gateway.options import GatewayProxyOptions
from fluxlit.gateway.options import gateway_opts as _gateway_opts
from fluxlit.gateway.paths import (
    normalize_root_mount,
    split_gateway_paths,
)
from fluxlit.gateway.paths import (
    strip_prefix_scope as _strip_prefix_scope,
)
from fluxlit.gateway.request_id import request_id_from_scope as _request_id_from_scope
from fluxlit.gateway.responses import not_found as _not_found
from fluxlit.gateway.upstream_http import (
    build_target_url as _build_target_url,
)
from fluxlit.gateway.upstream_http import (
    forwarded_upstream_header_pairs as _forwarded_upstream_header_pairs,
)
from fluxlit.gateway.upstream_http import (
    parse_ws_target as _parse_ws_target,
)
from fluxlit.gateway.upstream_http import (
    port_from_host_header as _port_from_host_header,
)
from fluxlit.gateway.upstream_http import (
    public_host_from_scope as _public_host_from_scope,
)
from fluxlit.gateway.upstream_http import (
    upstream_host_header as _upstream_host_header,
)
from fluxlit.gateway.websocket_proxy import proxy_websocket as _proxy_websocket

__all__ = [
    "GatewayProxyOptions",
    "build_gateway",
    "normalize_api_mount_path",
    "normalize_root_mount",
    "split_gateway_paths",
    "_build_target_url",
    "_filter_request_headers",
    "_forwarded_upstream_header_pairs",
    "_gateway_opts",
    "_not_found",
    "_parse_ws_target",
    "_port_from_host_header",
    "_proxy_http",
    "_proxy_websocket",
    "_public_host_from_scope",
    "_request_id_from_scope",
    "_strip_prefix_scope",
    "_upstream_host_header",
]
