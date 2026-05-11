"""Import target and gateway bind resolution for unified / sidecar mode."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fluxlit.app import FluxLit as FluxLitType


def resolve_import_target_for_unified(fl: FluxLitType) -> str:
    """Resolve ``module:attr`` for the Streamlit child and import stability.

    Order: :attr:`~fluxlit.app.FluxLit.import_target`, ``FLUXLIT_APP``, then project file
    (``fluxlit.toml`` / ``pyproject.toml``), then ``app:app``.
    """
    from fluxlit.config import load_project_config, resolve_target

    if fl.import_target:
        return fl.import_target.strip()
    env_t = (os.environ.get("FLUXLIT_APP") or "").strip()
    if env_t:
        return env_t
    return resolve_target(None, load_project_config())


def _gateway_bind_for_streamlit_child(fl: FluxLitType) -> tuple[str, int]:
    """Host/port the Streamlit sidecar uses to reach the API (loopback-safe URL)."""
    from fluxlit.config import load_project_config

    pc = load_project_config()
    bind_host = (os.environ.get("FLUXLIT_GATEWAY_HOST") or "").strip()
    if not bind_host and pc and pc.gateway_host:
        bind_host = pc.gateway_host.strip()
    if not bind_host:
        bind_host = fl.settings.gateway_host.strip()

    bind_port_s = (os.environ.get("FLUXLIT_GATEWAY_PORT") or "").strip()
    if bind_port_s:
        try:
            bind_port = int(bind_port_s)
        except ValueError:
            bind_port = fl.settings.gateway_port
    elif pc and pc.gateway_port is not None:
        bind_port = pc.gateway_port
    else:
        bind_port = fl.settings.gateway_port
    return bind_host, bind_port
