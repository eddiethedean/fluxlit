from __future__ import annotations

import importlib
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

import uvicorn

from fluxlit.gateway import build_gateway

if TYPE_CHECKING:
    from fluxlit.app import FluxLit


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def load_fluxlit(target: str) -> FluxLit:
    from fluxlit.app import FluxLit as FluxLitCls

    mod_name, sep, attr = target.partition(":")
    if not sep or not attr:
        msg = "App target must look like 'my_module:app'"
        raise ValueError(msg)
    module = importlib.import_module(mod_name)
    obj = getattr(module, attr)
    if not isinstance(obj, FluxLitCls):
        msg = f"{target} is not a FluxLit instance"
        raise TypeError(msg)
    return obj


def _wait_for_tcp(host: str, port: int, timeout_s: float = 30.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.05)
    msg = f"Timed out waiting for {host}:{port}"
    raise TimeoutError(msg)


def create_gateway_app() -> object:
    """Uvicorn factory (`--factory`): reads `FLUXLIT_APP` and `FLUXLIT_STREAMLIT_UPSTREAM`."""
    target = os.environ["FLUXLIT_APP"]
    upstream = os.environ["FLUXLIT_STREAMLIT_UPSTREAM"]
    fl = load_fluxlit(target)
    return build_gateway(fl.api, upstream)


def run_unified(
    target: str,
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = False,
) -> None:
    streamlit_port = find_free_port()
    runner = Path(__file__).resolve().parent / "streamlit_main.py"

    env = os.environ.copy()
    env["FLUXLIT_APP"] = target
    env["FLUXLIT_INTERNAL_API_BASE"] = f"http://{host}:{port}/api"

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(runner),
        "--server.headless",
        "true",
        "--server.port",
        str(streamlit_port),
        "--browser.gatherUsageStats",
        "false",
    ]
    proc = subprocess.Popen(cmd, env=env)
    try:
        _wait_for_tcp("127.0.0.1", streamlit_port)
        upstream = f"http://127.0.0.1:{streamlit_port}"
        os.environ["FLUXLIT_APP"] = target
        os.environ["FLUXLIT_STREAMLIT_UPSTREAM"] = upstream
        if reload:
            uvicorn.run(
                "fluxlit.runtime:create_gateway_app",
                host=host,
                port=port,
                factory=True,
                reload=True,
                log_level="info",
            )
        else:
            fl = load_fluxlit(target)
            uvicorn.run(build_gateway(fl.api, upstream), host=host, port=port, log_level="info")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
