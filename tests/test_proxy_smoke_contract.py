from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PROXY_DIR = REPO_ROOT / "docker" / "proxy-deployment"


def test_proxy_smoke_script_checks_0_6_contracts() -> None:
    script = (PROXY_DIR / "smoke-test.sh").read_text(encoding="utf-8")
    assert "/api/readyz" in script
    assert "/api/smoke" in script
    assert "/api/request-id" in script
    assert "fluxlit_smoke_ok" in script
    assert "expected 413" in script
    assert "_stcore/stream" in script


def test_proxy_matrix_runner_includes_all_supported_shapes() -> None:
    script = (PROXY_DIR / "run-all-proxy-smokes.sh").read_text(encoding="utf-8")
    assert "docker-compose.root.yml" in script
    assert "docker-compose.yml up" in script
    assert "docker-compose.fullpath.yml" in script
    assert "docker-compose.https.yml" in script
    assert 'PUBLIC_PREFIX=""' in script
    assert "trap cleanup EXIT" in script


def test_root_proxy_compose_and_nginx_contract() -> None:
    compose = (PROXY_DIR / "docker-compose.root.yml").read_text(encoding="utf-8")
    nginx = (PROXY_DIR / "nginx-root.conf").read_text(encoding="utf-8")
    assert "8082:80" in compose
    assert 'FLUXLIT_ROOT_PATH: ""' in compose
    assert "proxy_pass http://fluxlit" in nginx
    assert "location /" in nginx
