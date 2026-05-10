"""Process orchestration: load ``FluxLit`` by import path, spawn Streamlit, run Uvicorn."""

from __future__ import annotations

import contextlib
import importlib
import ipaddress
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
from pathlib import Path
from typing import TYPE_CHECKING, Any

import uvicorn
from starlette.types import ASGIApp

from fluxlit.gateway import build_gateway

if TYPE_CHECKING:
    from fluxlit.app import FluxLit


def find_free_port() -> int:
    """Bind to ``127.0.0.1:0`` and return the assigned ephemeral port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _loopback_http_host_for_client(bind_host: str) -> str:
    """Host segment for URLs used from the Streamlit subprocess to reach the gateway.

    ``0.0.0.0`` / empty bind addresses are valid for listening but invalid as HTTP
    client targets; use loopback. IPv6 literals are bracketed for RFC 3986 URLs.
    """
    h = bind_host.strip()
    if h in {"", "0.0.0.0"}:
        return "127.0.0.1"
    bare = h[1:-1] if h.startswith("[") and h.endswith("]") else h
    try:
        addr = ipaddress.ip_address(bare)
    except ValueError:
        return h
    if addr.is_unspecified:
        return "127.0.0.1"
    if isinstance(addr, ipaddress.IPv6Address):
        return f"[{addr}]"
    return str(addr)


def internal_api_base_url(*, bind_host: str, port: int, api_mount_path: str) -> str:
    """Build ``FLUXLIT_INTERNAL_API_BASE`` for the Streamlit child (same machine as gateway).

    ``bind_host`` is the Uvicorn bind address; the URL uses a loopback-safe host when
    needed so :class:`~fluxlit.client.ApiClient` can connect from the sidecar process.
    """
    path = api_mount_path if api_mount_path.startswith("/") else f"/{api_mount_path}"
    path = path.rstrip("/") or "/"
    netloc = f"{_loopback_http_host_for_client(bind_host)}:{port}"
    return urllib.parse.urlunparse(("http", netloc, path, "", "", ""))


def load_fluxlit(target: str) -> FluxLit:
    """Import ``module:attribute`` and ensure the object is a :class:`~fluxlit.app.FluxLit`.

    Raises:
        ValueError: If ``target`` is not a ``module:attr`` string.
        ImportError: If ``module`` cannot be imported.
        AttributeError: If ``module`` has no such attribute.
        TypeError: If ``attr`` is not a :class:`~fluxlit.app.FluxLit` instance.
    """
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
    """Block until ``host:port`` accepts a TCP connection or ``timeout_s`` elapses."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.05)
    msg = f"Timed out waiting for {host}:{port}"
    raise TimeoutError(msg)


def _build_streamlit_env(*, target: str, api_prefix: str, internal_api_base: str) -> dict[str, str]:
    """Clone ``os.environ`` and set ``FLUXLIT_*`` variables for the Streamlit subprocess."""
    env = os.environ.copy()
    env["FLUXLIT_APP"] = target
    env["FLUXLIT_API_PREFIX"] = api_prefix
    env["FLUXLIT_INTERNAL_API_BASE"] = internal_api_base
    return env


def _build_streamlit_cmd(*, runner: Path, port: int) -> list[str]:
    """Command line: ``python -m streamlit run <runner>`` with headless bind on ``port``."""
    return [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(runner),
        "--server.headless",
        "true",
        "--server.port",
        str(port),
        "--browser.gatherUsageStats",
        "false",
    ]


def _terminate_process(proc: subprocess.Popen[Any], *, timeout_s: float = 5.0) -> None:
    """Try graceful interrupt, then terminate, then kill."""
    if proc.poll() is not None:
        return

    # Prefer CTRL_BREAK_EVENT on Windows; SIGINT on Unix.
    if sys.platform.startswith("win"):
        with contextlib.suppress(Exception):
            proc.send_signal(getattr(signal, "CTRL_BREAK_EVENT"))  # noqa: B009
    else:
        with contextlib.suppress(Exception):
            proc.send_signal(signal.SIGINT)

    try:
        proc.wait(timeout=timeout_s)
        return
    except subprocess.TimeoutExpired:
        pass

    with contextlib.suppress(Exception):
        proc.terminate()
    try:
        proc.wait(timeout=timeout_s)
        return
    except subprocess.TimeoutExpired:
        pass

    with contextlib.suppress(Exception):
        proc.kill()


def create_gateway_app() -> ASGIApp:
    """ASGI factory for Uvicorn ``--factory`` reload mode.

    Reads ``FLUXLIT_APP`` (import target), ``FLUXLIT_STREAMLIT_UPSTREAM`` (Streamlit base URL),
    and ``FLUXLIT_API_PREFIX`` from the environment, then returns
    :func:`fluxlit.gateway.build_gateway` over the loaded FastAPI app.

    Returns:
        An ASGI3 callable (same contract as :func:`~fluxlit.gateway.build_gateway`).
    """
    target = os.environ["FLUXLIT_APP"]
    upstream = os.environ["FLUXLIT_STREAMLIT_UPSTREAM"]
    api_prefix = os.environ.get("FLUXLIT_API_PREFIX", "/api")
    fl = load_fluxlit(target)
    return build_gateway(fl.api, upstream, api_prefix=api_prefix)


def run_unified(
    target: str,
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = False,
    log_level: str = "info",
    proxy_headers: bool = False,
    forwarded_allow_ips: str | None = None,
) -> None:
    """Start Streamlit on a free localhost port and Uvicorn on ``host:port``.

    Sets process environment so ``create_gateway_app`` / Streamlit entry can resolve
    the app and internal API base (loopback-safe URL derived from ``host``, ``port``,
    and ``api_mount_path``). If Streamlit
    exits, the gateway is stopped. On shutdown, the Streamlit child receives SIGINT /
    terminate / kill (platform-dependent).

    Args:
        target: ``module:fluxlit_instance`` import path.
        host: Uvicorn bind host.
        port: Uvicorn bind port (public).
        reload: If True, use Uvicorn reload with :func:`create_gateway_app` (gateway only).
        log_level: Uvicorn log level.
        proxy_headers: Forwarded to :class:`uvicorn.Config`.
        forwarded_allow_ips: Forwarded to :class:`uvicorn.Config`.
    """
    streamlit_port = find_free_port()
    runner = Path(__file__).resolve().parent / "streamlit_main.py"

    fl = load_fluxlit(target)

    api_prefix = fl.settings.api_mount_path
    internal_api_base = internal_api_base_url(bind_host=host, port=port, api_mount_path=api_prefix)

    env = _build_streamlit_env(
        target=target,
        api_prefix=api_prefix,
        internal_api_base=internal_api_base,
    )
    cmd = _build_streamlit_cmd(runner=runner, port=streamlit_port)

    popen_kwargs: dict[str, Any] = {"env": env}
    if sys.platform.startswith("win"):
        # New process group so we can send CTRL_BREAK_EVENT.
        popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP")  # noqa: B009
    else:
        popen_kwargs["start_new_session"] = True

    proc: subprocess.Popen[Any] = subprocess.Popen(cmd, **popen_kwargs)
    try:
        _wait_for_tcp("127.0.0.1", streamlit_port)
        upstream = f"http://127.0.0.1:{streamlit_port}"
        os.environ["FLUXLIT_APP"] = target
        os.environ["FLUXLIT_STREAMLIT_UPSTREAM"] = upstream
        os.environ["FLUXLIT_API_PREFIX"] = api_prefix

        if reload:
            sys.stderr.write(
                "[fluxlit] --reload restarts the API gateway only; the Streamlit process "
                "does not reload. Restart fluxlit to apply Streamlit page changes.\n"
            )
            sys.stderr.flush()
            config = uvicorn.Config(
                "fluxlit.runtime:create_gateway_app",
                host=host,
                port=port,
                factory=True,
                reload=True,
                log_level=log_level,
                proxy_headers=proxy_headers,
                forwarded_allow_ips=forwarded_allow_ips,
            )
        else:
            config = uvicorn.Config(
                build_gateway(fl.api, upstream, api_prefix=fl.settings.api_mount_path),
                host=host,
                port=port,
                log_level=log_level,
                proxy_headers=proxy_headers,
                forwarded_allow_ips=forwarded_allow_ips,
            )

        server = uvicorn.Server(config)

        def monitor_streamlit() -> None:
            code = proc.wait()
            if not server.should_exit:
                sys.stderr.write(f"[fluxlit] Streamlit exited (code={code}); stopping gateway.\n")
                sys.stderr.flush()
                server.should_exit = True

        threading.Thread(target=monitor_streamlit, daemon=True).start()
        server.run()
    finally:
        _terminate_process(proc)
