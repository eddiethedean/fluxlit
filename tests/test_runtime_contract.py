"""Black-box checks for ``run_unified`` (subprocess). Marked ``slow`` — not in default matrix."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from fluxlit.runtime import find_free_port

REPO_ROOT = Path(__file__).resolve().parents[1]
TARGET = "tests.e2e.minimal_app:app"


@pytest.mark.slow
def test_run_unified_subprocess_serves_api_healthz() -> None:
    port = find_free_port()
    env = os.environ.copy()
    env["FLUXLIT_NO_PIDFILE"] = "1"
    prev = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(REPO_ROOT) if not prev else f"{REPO_ROOT}{os.pathsep}{prev}"

    code = (
        "from fluxlit.runtime import run_unified; "
        f"run_unified({TARGET!r}, host='127.0.0.1', port={port}, write_pidfile=False)"
    )
    proc = subprocess.Popen(  # noqa: S603
        [sys.executable, "-c", code],
        env=env,
        cwd=str(REPO_ROOT),
    )
    try:
        deadline = time.monotonic() + 120.0
        last_exc: Exception | None = None
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                pytest.fail(f"fluxlit subprocess exited early (code={proc.returncode})")
            try:
                r = httpx.get(f"http://127.0.0.1:{port}/api/healthz", timeout=1.0)
            except httpx.HTTPError as e:
                last_exc = e
                time.sleep(0.2)
                continue
            if r.status_code == 200 and r.json().get("status") == "ok":
                return
            time.sleep(0.2)
        msg = f"Gateway did not become ready: {last_exc}"
        pytest.fail(msg)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=30.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10.0)
