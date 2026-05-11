"""Upstream HTTP/WebSocket tuning options for the gateway."""

from __future__ import annotations

from dataclasses import dataclass

from fluxlit.config import FluxlitSettings


@dataclass(frozen=True)
class GatewayProxyOptions:
    """Upstream HTTP/WebSocket tuning for :func:`fluxlit.gateway.build_gateway`.

    Mirrors :class:`~fluxlit.config.FluxlitSettings` gateway fields.
    """

    connect_timeout: float = 30.0
    read_timeout: float = 120.0
    max_proxy_body_bytes: int = 0
    max_concurrent_upstream_http: int = 0
    httpx_max_connections: int = 0
    httpx_max_keepalive_connections: int = 0
    ws_open_timeout_s: float = 30.0
    ws_ping_interval_s: float | None = None
    ws_ping_timeout_s: float | None = None
    ws_close_timeout_s: float | None = None
    ws_max_message_bytes: int | None = None


def gateway_opts(fluxlit_settings: FluxlitSettings | None) -> GatewayProxyOptions:
    if fluxlit_settings is None:
        return GatewayProxyOptions()
    fs = fluxlit_settings
    return GatewayProxyOptions(
        connect_timeout=fs.gateway_upstream_connect_timeout_s,
        read_timeout=fs.gateway_upstream_read_timeout_s,
        max_proxy_body_bytes=fs.gateway_max_proxy_request_body_bytes,
        max_concurrent_upstream_http=fs.gateway_max_concurrent_upstream_http,
        httpx_max_connections=fs.gateway_httpx_max_connections,
        httpx_max_keepalive_connections=fs.gateway_httpx_max_keepalive_connections,
        ws_open_timeout_s=fs.gateway_ws_open_timeout_s,
        ws_ping_interval_s=fs.gateway_ws_ping_interval_s,
        ws_ping_timeout_s=fs.gateway_ws_ping_timeout_s,
        ws_close_timeout_s=fs.gateway_ws_close_timeout_s,
        ws_max_message_bytes=fs.gateway_ws_max_message_bytes,
    )
