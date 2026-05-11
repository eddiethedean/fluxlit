from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from fluxlit.runtime import find_free_port

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_shell_scripts_parse() -> None:
    scripts = [
        "scripts/soak_http.sh",
        "scripts/run_smoke_app.sh",
        "scripts/chaos_streamlit_kill.sh",
        "scripts/chaos_slow_upstream.sh",
        "scripts/chaos_oversized_body.sh",
        "scripts/chaos_dropped_websocket.sh",
        "scripts/chaos_graceful_shutdown.sh",
        "docker/proxy-deployment/smoke-test.sh",
        "docker/proxy-deployment/run-all-proxy-smokes.sh",
    ]
    subprocess.run(["bash", "-n", *scripts], cwd=REPO_ROOT, check=True)


def test_soak_http_json_output_against_local_server(tmp_path: Path) -> None:
    port = find_free_port()
    server = subprocess.Popen(  # noqa: S603
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=tmp_path,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 5
        while True:
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=0.5)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.1)
        env = os.environ.copy()
        env.update(
            {
                "BASE_URL": f"http://127.0.0.1:{port}",
                "PATH_SUFFIX": "/",
                "COUNT": "3",
                "OUTPUT_FORMAT": "json",
            }
        )
        result = subprocess.run(
            ["bash", "scripts/soak_http.sh"],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=True,
            timeout=20,
        )
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)

    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["count"] == 3
    assert payload["ok"] == 3
    assert payload["fail"] == 0
    assert payload["path"] == "/"
    assert payload["p50_ms"] <= payload["p95_ms"] <= payload["p99_ms"]
