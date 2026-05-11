from __future__ import annotations

import os
import subprocess
import sys
import time
from collections.abc import Generator
from pathlib import Path

import httpx
import pytest

from fluxlit.runtime import find_free_port

REPO_ROOT = Path(__file__).resolve().parents[2]
TARGET = "tests.e2e.minimal_app:app"


def _wait_for_health(
    base_url: str,
    *,
    health_path: str = "/api/healthz",
    timeout_s: float = 90.0,
) -> None:
    url = f"{base_url.rstrip('/')}{health_path}"
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            r = httpx.get(url, timeout=1.0)
        except httpx.HTTPError:
            time.sleep(0.2)
            continue
        if r.status_code == 200:
            return
        time.sleep(0.2)
    msg = f"Gateway did not become ready within {timeout_s}s: {url}"
    raise RuntimeError(msg)


@pytest.fixture(scope="session")
def fluxlit_live_url() -> Generator[str, None, None]:
    port = find_free_port()
    env = os.environ.copy()
    env["FLUXLIT_NO_PIDFILE"] = "1"
    prev_py = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(REPO_ROOT) if not prev_py else f"{REPO_ROOT}{os.pathsep}{prev_py}"

    code = (
        "from fluxlit.runtime import run_unified; "
        f"run_unified({TARGET!r}, host='127.0.0.1', port={port}, write_pidfile=False)"
    )
    proc = subprocess.Popen(  # noqa: S603
        [sys.executable, "-c", code],
        env=env,
        cwd=str(REPO_ROOT),
    )
    base = f"http://127.0.0.1:{port}"
    try:
        if proc.poll() is not None:
            msg = f"FluxLit subprocess exited early (code={proc.returncode})"
            raise RuntimeError(msg)
        _wait_for_health(base)
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5.0)


@pytest.fixture(scope="session")
def fluxlit_live_subpath_url() -> Generator[str, None, None]:
    """``FLUXLIT_ROOT_PATH=/e2eapp`` — browser uses ``/e2eapp/`` for Streamlit and API."""
    port = find_free_port()
    env = os.environ.copy()
    env["FLUXLIT_NO_PIDFILE"] = "1"
    env["FLUXLIT_ROOT_PATH"] = "/e2eapp"
    prev_py = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(REPO_ROOT) if not prev_py else f"{REPO_ROOT}{os.pathsep}{prev_py}"

    code = (
        "from fluxlit.runtime import run_unified; "
        f"run_unified({TARGET!r}, host='127.0.0.1', port={port}, write_pidfile=False)"
    )
    proc = subprocess.Popen(  # noqa: S603
        [sys.executable, "-c", code],
        env=env,
        cwd=str(REPO_ROOT),
    )
    base = f"http://127.0.0.1:{port}"
    try:
        if proc.poll() is not None:
            msg = f"FluxLit subprocess exited early (code={proc.returncode})"
            raise RuntimeError(msg)
        _wait_for_health(base, health_path="/e2eapp/api/healthz")
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5.0)
