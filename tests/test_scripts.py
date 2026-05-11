from __future__ import annotations

import subprocess
from pathlib import Path

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
