"""Public path prefix and API mount routing helpers."""

from __future__ import annotations

from starlette.types import Scope


def normalize_root_mount(raw: str) -> str:
    """Normalize a public URL prefix (e.g. Posit Connect content path) for routing.

    Returns ``""`` when unset, otherwise a path starting with ``/`` and no trailing
    slash (except root ``"/"`` is not used — empty means no mount).
    """
    s = (raw or "").strip()
    if not s:
        return ""
    if not s.startswith("/"):
        s = f"/{s}"
    return s.rstrip("/") or ""


def split_gateway_paths(path: str, root_mount: str) -> tuple[str, str]:
    """Split the ASGI path for dispatch vs Streamlit upstream.

    Some reverse proxies forward the **full** public path (``/content/123/api/...``).
    Others strip the mount and only forward the suffix (``/api/...``) while setting
    ASGI ``root_path``. :func:`normalize_root_mount` should match the browser-visible
    prefix configured for Streamlit ``server.baseUrlPath``.

    Returns:
        ``(dispatch_path, streamlit_path)`` — use *dispatch_path* to choose API vs
        Streamlit; send *streamlit_path* to the Streamlit sidecar when proxying.
    """
    m = normalize_root_mount(root_mount)
    p = path if path.startswith("/") else f"/{path}"
    if not m:
        return p, p
    if p == m or p.startswith(f"{m}/"):
        rest = "/" if p == m else p[len(m) :]
        if not rest.startswith("/"):
            rest = f"/{rest}"
        return rest, p
    return p, f"{m}{p}"


def location_under_mount(mount: str, suffix: str) -> str:
    """Build a root-absolute Location (``/app/api/docs``) when mounted under ``/app``."""
    m = normalize_root_mount(mount)
    s = suffix if suffix.startswith("/") else f"/{suffix}"
    return f"{m}{s}" if m else s


def strip_prefix_scope(scope: Scope, prefix: str) -> Scope:
    """Strip ``prefix`` from the URL path and extend ``root_path`` (ASGI).

    FastAPI's Swagger / ReDoc handlers build ``openapi_url`` as
    ``scope["root_path"] + app.openapi_url``. Without setting ``root_path`` to the
    gateway's API mount (e.g. ``/api``), the embedded URL is ``/openapi.json``; the
    browser then requests the **gateway** root, which is proxied to Streamlit — not
    JSON — and Swagger UI reports a missing OpenAPI version.
    """
    path = scope.get("path") or "/"
    rest = path.removeprefix(prefix) or "/"
    new_scope: Scope = dict(scope)
    new_scope["path"] = rest
    new_scope["raw_path"] = rest.encode("latin-1")
    prior = (scope.get("root_path") or "").rstrip("/")
    mount = prefix.rstrip("/")
    new_scope["root_path"] = f"{prior}{mount}" if prior else mount
    return new_scope
