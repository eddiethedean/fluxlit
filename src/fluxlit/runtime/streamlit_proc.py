"""Streamlit sidecar command, environment, and graceful process termination."""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TypedDict

from fluxlit.gateway import normalize_root_mount


class _StreamlitPopenKwargs(TypedDict, total=False):
    env: Mapping[str, str]
    creationflags: int
    start_new_session: bool


def _build_streamlit_env(*, target: str, api_prefix: str, internal_api_base: str) -> dict[str, str]:
    """Clone ``os.environ`` and set ``FLUXLIT_*`` variables for the Streamlit subprocess."""
    env = os.environ.copy()
    env["FLUXLIT_APP"] = target
    env["FLUXLIT_API_PREFIX"] = api_prefix
    env["FLUXLIT_INTERNAL_API_BASE"] = internal_api_base
    return env


def _validate_streamlit_extra_cli_args(args: Sequence[str] | None) -> None:
    """Reject CLI flags that would break FluxLit's sidecar contract (bind, port, base path).

    Extra args are appended *after* FluxLit flags, so Streamlit would honor overrides for
    port/address/baseUrlPath and the parent would still wait on the wrong port or URL.
    """
    if not args:
        return
    forbid = frozenset({"--server.port", "--server.address", "--server.baseUrlPath"})
    eq_prefixes = ("--server.port=", "--server.address=", "--server.baseUrlPath=")
    for a in args:
        if a.startswith(eq_prefixes):
            msg = (
                "streamlit_run_cli_args must not set server.port, server.address, or "
                f"server.baseUrlPath (FluxLit owns the sidecar bind and public path); got {a!r}"
            )
            raise ValueError(msg)
        if a in forbid:
            msg = (
                "streamlit_run_cli_args must not include "
                f"{a!r} (use FLUXLIT_ROOT_PATH / settings for the public mount; "
                "FluxLit assigns the sidecar port)."
            )
            raise ValueError(msg)


def _build_streamlit_cmd(
    *,
    runner: Path,
    port: int,
    base_url_path: str = "",
    extra_cli_args: Sequence[str] | None = None,
) -> list[str]:
    """Command line: ``python -m streamlit run <runner>`` with headless bind on ``port``.

    Streamlit binds only to loopback on an ephemeral port; the browser talks to the
    FluxLit gateway. Disabling XSRF on this hop avoids Streamlit forcing CORS on when
    XSRF is enabled (noisy warnings and brittle proxy handshakes). CORS stays off
    because cross-origin browser traffic should not hit the sidecar directly.

    ``extra_cli_args`` (from :attr:`~fluxlit.config.FluxlitSettings.streamlit_run_cli_args`)
    are appended last so callers can override theme, logging level, etc., per Streamlit CLI.
    """
    _validate_streamlit_extra_cli_args(extra_cli_args)
    cmd: list[str] = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(runner),
        "--server.headless",
        "true",
        "--server.port",
        str(port),
        "--server.address",
        "127.0.0.1",
        "--server.enableXsrfProtection",
        "false",
        "--server.enableCORS",
        "false",
        "--browser.gatherUsageStats",
        "false",
    ]
    m = normalize_root_mount(base_url_path)
    if m:
        cmd.extend(["--server.baseUrlPath", m])
    if extra_cli_args:
        cmd.extend(list(extra_cli_args))
    return cmd


def _terminate_process(proc: subprocess.Popen[bytes], *, timeout_s: float = 5.0) -> None:
    """Try graceful interrupt, then terminate, then kill."""
    if proc.poll() is not None:
        return

    # Prefer CTRL_BREAK_EVENT on Windows; SIGINT on Unix.
    if sys.platform.startswith("win"):
        with contextlib.suppress(Exception):
            proc.send_signal(getattr(signal, "CTRL_BREAK_EVENT"))  # noqa: B009
    else:  # pragma: no cover
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
