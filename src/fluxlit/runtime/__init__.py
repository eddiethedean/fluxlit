"""Process orchestration: load ``FluxLit`` by import path, spawn Streamlit, run Uvicorn."""

from __future__ import annotations

import socket  # noqa: F401 — tests patch ``fluxlit.runtime.socket.*``
import subprocess  # noqa: F401 — tests patch ``fluxlit.runtime.subprocess.Popen``
import time  # noqa: F401 — tests patch ``fluxlit.runtime.time.*``

from fluxlit.runtime.constants import _STREAMLIT_TCP_WAIT_S, DEFAULT_PIDFILE_NAME
from fluxlit.runtime.import_target import (
    find_free_port,
    internal_api_base_url,
    load_fluxlit,
)
from fluxlit.runtime.orchestrate import (
    asgi_from_fluxlit,
    create_gateway_app,
    create_unified_app,
)
from fluxlit.runtime.process_control import default_pidfile_path, shutdown_unified_process
from fluxlit.runtime.public_mount import _inject_public_root_path
from fluxlit.runtime.reload_watcher import _start_streamlit_reload_watcher
from fluxlit.runtime.resolve import resolve_import_target_for_unified
from fluxlit.runtime.streamlit_proc import (
    _build_streamlit_cmd,
    _build_streamlit_env,
    _terminate_process,
    _validate_streamlit_extra_cli_args,
)
from fluxlit.runtime.upstream_state import (
    STREAMLIT_UPSTREAM_FILE_ENV,
    read_streamlit_upstream_url,
    update_streamlit_upstream_file,
    write_streamlit_upstream_state,
)
from fluxlit.runtime.uvicorn_runner import run_unified
from fluxlit.runtime.wait_tcp import _wait_for_tcp

__all__ = [
    "DEFAULT_PIDFILE_NAME",
    "STREAMLIT_UPSTREAM_FILE_ENV",
    "_STREAMLIT_TCP_WAIT_S",
    "_build_streamlit_cmd",
    "_build_streamlit_env",
    "_inject_public_root_path",
    "_start_streamlit_reload_watcher",
    "_terminate_process",
    "_validate_streamlit_extra_cli_args",
    "_wait_for_tcp",
    "asgi_from_fluxlit",
    "create_gateway_app",
    "create_unified_app",
    "default_pidfile_path",
    "find_free_port",
    "internal_api_base_url",
    "load_fluxlit",
    "read_streamlit_upstream_url",
    "resolve_import_target_for_unified",
    "run_unified",
    "shutdown_unified_process",
    "update_streamlit_upstream_file",
    "write_streamlit_upstream_state",
]
