"""Posit Workbench / Posit Connect-style bind hints (subpath + trusted proxy headers)."""

from __future__ import annotations

from fluxlit.api_mount import normalize_api_mount_path

__all__ = [
    "browser_base_url",
    "format_workbench_startup_message",
    "loopback_browser_host",
]


def loopback_browser_host(bind_host: str) -> str:
    """Return a host string suitable for pasting into a browser on the same machine.

    Binds like ``0.0.0.0`` or ``::`` are shown as ``127.0.0.1`` so operators get a
    clickable URL while Uvicorn still listens on all interfaces.
    """
    h = (bind_host or "").strip()
    if h in {"0.0.0.0", "::", "[::]"}:
        return "127.0.0.1"
    return h or "127.0.0.1"


def browser_base_url(bind_host: str, bind_port: int, *, scheme: str = "http") -> str:
    """Build ``scheme://host:port`` for operator hints (not OAuth canonical URL)."""
    host = loopback_browser_host(bind_host)
    sch = (scheme or "http").strip() or "http"
    return f"{sch}://{host}:{int(bind_port)}"


def _api_prefix_display(api_mount_path: str) -> str:
    return normalize_api_mount_path(api_mount_path)


def format_workbench_startup_message(
    *,
    app_title: str,
    bind_host: str,
    bind_port: int,
    root_mount_norm: str,
    api_mount_path: str,
    public_base_url: str,
    proxy_headers_on: bool,
) -> str:
    """Human-readable startup banner for ``fluxlit workbench`` / ``--workbench``."""
    base = browser_base_url(bind_host, bind_port)
    mount = root_mount_norm.strip()
    api = _api_prefix_display(api_mount_path)
    lines: list[str] = [
        "[fluxlit] Workbench/Connect mode: Uvicorn proxy_headers is ON "
        "(trust only your edge reverse proxy).",
        f"[fluxlit] App title: {app_title or 'FluxLit'}",
    ]
    if proxy_headers_on:
        lines.append("[fluxlit] X-Forwarded-* headers will be honored for scheme/host/client IP.")
    home = f"{base}{mount}/" if mount else f"{base}/"
    lines.append(f"[fluxlit] Open in browser (loopback): {home}")
    suffix = f"{mount}{api}" if mount else api
    lines.append(f"[fluxlit] API liveness: {base}{suffix}/healthz")
    lines.append(f"[fluxlit] API docs: {base}{suffix}/docs")
    if not mount:
        lines.append(
            "[fluxlit] Hint: set FLUXLIT_ROOT_PATH when users reach this app under a "
            "subpath (Posit Connect content URL, Workbench published path, etc.)."
        )
    pb = public_base_url.strip()
    if pb:
        lines.append(
            f"[fluxlit] OAuth / canonical public URL: {pb} "
            "(see FLUXLIT_PUBLIC_BASE_URL in configuration docs)."
        )
    lines.append(
        "[fluxlit] Tighten FLUXLIT_FORWARDED_ALLOW_IPS in production when the proxy IP "
        "range is known."
    )
    return "\n".join(lines) + "\n"
