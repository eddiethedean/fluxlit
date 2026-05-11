"""High-level ASGI factories: gateway-from-env, unified FluxLit stack."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from starlette.types import ASGIApp

from fluxlit.gateway import build_gateway, normalize_root_mount
from fluxlit.runtime.import_target import (
    find_free_port,
    internal_api_base_url,
    load_fluxlit,
)
from fluxlit.runtime.lifespan_bridge import build_unified_fluxlit_asgi_app
from fluxlit.runtime.public_mount import _inject_public_root_path
from fluxlit.runtime.resolve import _gateway_bind_for_streamlit_child
from fluxlit.runtime.streamlit_proc import _build_streamlit_cmd, _build_streamlit_env
from fluxlit.runtime.upstream_state import read_streamlit_upstream_url

if TYPE_CHECKING:
    from fluxlit.app import FluxLit as FluxLitType

_STREAMLIT_MAIN = Path(__file__).resolve().parent.parent / "streamlit" / "main.py"


def create_gateway_app() -> ASGIApp:
    """ASGI factory for Uvicorn ``--factory`` reload mode.

    Reads ``FLUXLIT_APP`` (import target), Streamlit upstream from
    ``FLUXLIT_STREAMLIT_UPSTREAM_FILE`` or ``FLUXLIT_STREAMLIT_UPSTREAM``, and
    ``FLUXLIT_API_PREFIX`` from the environment, then returns
    :func:`fluxlit.gateway.build_gateway` over the loaded FastAPI app.

    Returns:
        An ASGI3 callable (same contract as :func:`~fluxlit.gateway.build_gateway`).

    Raises:
        RuntimeError: If ``FLUXLIT_APP`` is unset or the upstream URL cannot be resolved.
    """
    if not (os.environ.get("FLUXLIT_APP") or "").strip():
        msg = (
            "Missing required environment variable FLUXLIT_APP. "
            "Set it before using `create_gateway_app` with Uvicorn --factory "
            "(normally set by `fluxlit dev` / `fluxlit run`)."
        )
        raise RuntimeError(msg)
    if not read_streamlit_upstream_url():
        msg = (
            "Missing Streamlit upstream URL. Set FLUXLIT_STREAMLIT_UPSTREAM and/or "
            "FLUXLIT_STREAMLIT_UPSTREAM_FILE (normally set by `fluxlit dev` / `fluxlit run`)."
        )
        raise RuntimeError(msg)
    target = os.environ["FLUXLIT_APP"].strip()
    api_prefix = os.environ.get("FLUXLIT_API_PREFIX", "/api")
    fl = load_fluxlit(target)
    mount = normalize_root_mount(fl.settings.public_mount_path())
    return _inject_public_root_path(
        build_gateway(
            fl.api,
            "",
            upstream_resolver=read_streamlit_upstream_url,
            access_log=fl.settings.enable_gateway_access_log,
            api_prefix=api_prefix,
            root_mount=mount,
            proxy_settings=fl.settings,
        ),
        mount,
    )


def asgi_from_fluxlit(fl: FluxLitType, import_target: str) -> ASGIApp:
    """Build unified ASGI (gateway + Streamlit) for an existing :class:`~fluxlit.app.FluxLit`.

    Use when you already hold the instance (e.g. ``uvicorn main:app``). *import_target*
    must be the ``module:attr`` the Streamlit subprocess imports; use
    :func:`fluxlit.runtime.resolve_import_target_for_unified` or set
    :attr:`~fluxlit.app.FluxLit.import_target` / ``fluxlit.toml`` / ``FLUXLIT_APP``.

    Behavior matches :func:`create_unified_app` (lifespan, sidecar, inner FastAPI hooks).
    """
    target = import_target.strip()
    if not target:
        msg = "import_target for unified ASGI must be a non-empty module:attr string"
        raise ValueError(msg)

    api_prefix = fl.settings.api_mount_path
    mount = normalize_root_mount(fl.settings.public_mount_path())

    internal = (os.environ.get("FLUXLIT_INTERNAL_API_BASE") or "").strip()
    if not internal:
        bind_host, bind_port = _gateway_bind_for_streamlit_child(fl)
        internal = internal_api_base_url(
            bind_host=bind_host,
            port=bind_port,
            api_mount_path=api_prefix,
        )

    streamlit_port = find_free_port()
    pub = fl.settings.public_mount_path()
    cmd = _build_streamlit_cmd(
        runner=_STREAMLIT_MAIN,
        port=streamlit_port,
        base_url_path=pub,
        extra_cli_args=fl.settings.streamlit_run_cli_args,
    )
    env = _build_streamlit_env(target=target, api_prefix=api_prefix, internal_api_base=internal)

    upstream_url_box: list[str] = [""]

    def resolve_upstream() -> str:
        return upstream_url_box[0]

    gateway_app: ASGIApp = build_gateway(
        fl.api,
        "",
        upstream_resolver=resolve_upstream,
        access_log=fl.settings.enable_gateway_access_log,
        api_prefix=api_prefix,
        root_mount=mount,
        proxy_settings=fl.settings,
    )
    gateway_app = _inject_public_root_path(gateway_app, mount)

    return build_unified_fluxlit_asgi_app(
        fl,
        gateway_app=gateway_app,
        cmd=cmd,
        env=env,
        streamlit_port=streamlit_port,
        upstream_url_box=upstream_url_box,
    )


def create_unified_app() -> ASGIApp:
    """ASGI factory for Uvicorn ``--factory`` (same stack as :meth:`fluxlit.app.FluxLit.__call__`).

    Requires ``FLUXLIT_APP=module:attr``. Prefer ``uvicorn main:app`` when ``app`` is a
    :class:`~fluxlit.app.FluxLit` instance so you do not need this factory or env indirection.
    """
    if not (os.environ.get("FLUXLIT_APP") or "").strip():
        msg = (
            "Missing required environment variable FLUXLIT_APP. "
            "Set it before using `create_unified_app` with Uvicorn --factory."
        )
        raise RuntimeError(msg)
    target = os.environ["FLUXLIT_APP"].strip()
    fl = load_fluxlit(target)
    return asgi_from_fluxlit(fl, target)
