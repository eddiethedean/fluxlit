"""Upstream URL and forwarding header construction for HTTP/WebSocket proxy hops."""

from __future__ import annotations

import urllib.parse

from starlette.types import Scope


def build_target_url(scope: Scope, upstream: str, *, path: str | None = None) -> str:
    use_path = path if path is not None else (scope.get("path") or "/")
    query = scope.get("query_string", b"").decode("latin-1")
    if query:
        return f"{upstream}{use_path}?{query}"
    return f"{upstream}{use_path}"


def upstream_host_header(upstream: str) -> str:
    parsed = urllib.parse.urlparse(upstream)
    if parsed.port:
        return f"{parsed.hostname}:{parsed.port}"
    return parsed.hostname or "127.0.0.1"


def public_host_from_scope(scope: Scope, upstream: str) -> str:
    """Host header the browser used (gateway); fallback to upstream netloc."""
    for k, v in scope.get("headers") or []:
        if k.lower() == b"host":
            return v.decode("latin-1").strip() or upstream_host_header(upstream)
    return upstream_host_header(upstream)


def port_from_host_header(host_val: str) -> int | None:
    """Parse a port from ``Host`` (supports ``[ipv6]:port``)."""
    if host_val.startswith("["):
        if "]:" in host_val:
            rest = host_val.split("]:", 1)[1]
            return int(rest) if rest.isdigit() else None
        return None
    if ":" in host_val:
        maybe_port = host_val.rsplit(":", 1)[1]
        if maybe_port.isdigit():
            return int(maybe_port)
    return None


def forwarded_upstream_header_pairs(
    scope: Scope,
    public_host: str,
    *,
    forwarded_prefix: str | None = None,
) -> list[tuple[str, str]]:
    """Headers that describe the client-facing URL (for servers that read ``X-Forwarded-*``)."""
    proto = scope.get("scheme") or "http"
    pairs: list[tuple[str, str]] = [
        ("X-Forwarded-Host", public_host),
        ("X-Forwarded-Proto", proto),
    ]
    port = port_from_host_header(public_host)
    if port is not None:
        pairs.append(("X-Forwarded-Port", str(port)))
    if forwarded_prefix:
        pairs.append(("X-Forwarded-Prefix", forwarded_prefix))
    client = scope.get("client")
    if isinstance(client, (list, tuple)) and len(client) >= 1 and client[0]:
        pairs.append(("X-Forwarded-For", client[0]))
    return pairs


def parse_ws_target(scope: Scope, upstream: str, *, path: str | None = None) -> str:
    use_path = path if path is not None else (scope.get("path") or "/")
    qs = scope.get("query_string", b"")
    if qs:
        use_path = f"{use_path}?{qs.decode('latin-1')}"
    parsed = urllib.parse.urlparse(upstream)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port
    netloc = f"{host}:{port}" if port else host
    base_path = parsed.path.rstrip("/")
    full_path = f"{base_path}{use_path}" if base_path else use_path
    return str(urllib.parse.urlunparse((scheme, netloc, full_path, "", "", "")))
