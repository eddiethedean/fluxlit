from __future__ import annotations

import contextlib
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from fluxlit.cli import app


def test_doctor_prints_checks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module_path = tmp_path / "demo_cli_app.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n\n"
        "app = FluxLit(title='CLI App', settings=FluxlitSettings(gateway_port=59201))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "demo_cli_app:app"])
    assert res.exit_code == 0
    assert "FluxLit doctor" in res.stdout
    assert "PASS" in res.stdout
    assert "import_target:" in res.stdout
    assert "demo_cli_app:app" in res.stdout


def test_doctor_warns_when_internal_api_path_mismatches_mount(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = tmp_path / "doc_mount_app.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n\n"
        "app = FluxLit(title='M', settings=FluxlitSettings("
        "api_mount_path='/api/v1', gateway_port=59203))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FLUXLIT_INTERNAL_API_BASE", "http://127.0.0.1:59203/api")

    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "doc_mount_app:app"])
    assert res.exit_code == 0
    assert "WARN" in res.stdout
    assert "api_mount_path" in res.stdout


def test_doctor_passes_proxy_headers_when_subpath_and_trust_proxy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = tmp_path / "doc_subpath_trust_ok.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n\n"
        "app = FluxLit(title='ST', settings=FluxlitSettings("
        "root_path='/content/1', trust_proxy=True, public_base_url='https://example.com', "
        "gateway_port=59278))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "doc_subpath_trust_ok:app"])
    assert res.exit_code == 0
    assert "proxy_headers" in res.stdout
    assert "PASS" in res.stdout
    assert "trust_proxy enabled" in res.stdout


def test_doctor_warns_when_trust_proxy_has_broad_forwarded_allow_ips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = tmp_path / "doc_proxy_broad.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n\n"
        "app = FluxLit(settings=FluxlitSettings("
        "trust_proxy=True, forwarded_allow_ips='*', gateway_port=59279))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "doc_proxy_broad:app"])
    assert res.exit_code == 0
    assert "forwarded_allow_ips" in res.stdout
    assert "WARN" in res.stdout


def test_doctor_warns_when_public_base_url_path_mismatches_root_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = tmp_path / "doc_public_base_mismatch.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n\n"
        "app = FluxLit(settings=FluxlitSettings("
        "root_path='/apps/demo', public_base_url='https://example.com/wrong', "
        "gateway_port=59280))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "doc_public_base_mismatch:app"])
    assert res.exit_code == 0
    assert "public_base_url" in res.stdout
    assert "does not match public mount" in res.stdout


def test_doctor_fails_missing_streamlit_upstream_state_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = tmp_path / "doc_missing_upstream_file.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n\n"
        "app = FluxLit(settings=FluxlitSettings(gateway_port=59281))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv("FLUXLIT_STREAMLIT_UPSTREAM_FILE", str(tmp_path / "missing.txt"))
    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "doc_missing_upstream_file:app"])
    assert res.exit_code == 1
    assert "streamlit_upstream_state" in res.stdout
    assert "state file missing" in res.stdout


def test_doctor_fails_fluxlit_auth_extra_when_pyjwt_unimportable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module_path = tmp_path / "doc_jwt_blocked.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n\n"
        "app = FluxLit(title='B', settings=FluxlitSettings(gateway_port=59301))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv("FLUXLIT_JWT_ISSUER", "https://issuer.blocked")
    prior = sys.modules.pop("jwt", None)
    sys.modules["jwt"] = None
    try:
        runner = CliRunner()
        res = runner.invoke(app, ["doctor", "doc_jwt_blocked:app"])
        assert res.exit_code == 1
        assert "fluxlit_auth_extra" in res.stdout
        assert "FAIL" in res.stdout
    finally:
        sys.modules.pop("jwt", None)
        if prior is not None:
            sys.modules["jwt"] = prior


def test_doctor_reports_auth_extra_when_jwt_env_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = tmp_path / "doc_jwt_env.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n\n"
        "app = FluxLit(title='J', settings=FluxlitSettings(gateway_port=59299))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv("FLUXLIT_JWT_ISSUER", "https://issuer.example")
    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "doc_jwt_env:app"])
    assert res.exit_code == 0
    assert "fluxlit_auth_extra" in res.stdout
    assert "PyJWT" in res.stdout


def test_doctor_warns_when_subpath_without_trust_proxy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = tmp_path / "doc_subpath_proxy.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n\n"
        "app = FluxLit(title='S', settings=FluxlitSettings("
        "root_path='/content/1', trust_proxy=False, public_base_url='https://example.com', "
        "gateway_port=59277))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "doc_subpath_proxy:app"])
    assert res.exit_code == 0
    assert "proxy_headers" in res.stdout
    assert "FLUXLIT_TRUST_PROXY" in res.stdout


def test_doctor_passes_when_internal_api_path_matches_mount(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = tmp_path / "doc_mount_ok.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n\n"
        "app = FluxLit(title='M', settings=FluxlitSettings("
        "api_mount_path='/api/v1', gateway_port=59204))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FLUXLIT_INTERNAL_API_BASE", "http://127.0.0.1:59204/api/v1")

    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "doc_mount_ok:app"])
    assert res.exit_code == 0
    assert "FLUXLIT_INTERNAL_API_BASE" in res.stdout
    assert "matches api_mount_path" in res.stdout


def test_doctor_exit_one_on_failure_without_warnings_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = tmp_path / "broken_app2.py"
    module_path.write_text("# not a FluxLit instance\napp = 123\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))

    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "broken_app2:app"])
    assert res.exit_code == 1
    assert "FAIL" in res.stdout


def test_doctor_warnings_only_exit_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module_path = tmp_path / "broken_app.py"
    module_path.write_text("# not a FluxLit instance\napp = 123\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))

    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "broken_app:app", "--warnings-only"])
    assert res.exit_code == 0
    assert "FAIL" in res.stdout


def test_dev_invalid_reload_scope_exits_two(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "reload_app.py").write_text(
        "from fluxlit import FluxLit\napp = FluxLit(title='R')\n", encoding="utf-8"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    res = runner.invoke(
        app,
        ["dev", "reload_app:app", "--reload", "--reload-scope", "bogus"],
        catch_exceptions=False,
    )
    assert res.exit_code == 2
    assert "reload-scope" in res.stderr.lower()


def test_dev_passes_reload_scope_full_to_run_unified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "reload_full_app.py").write_text(
        "from fluxlit import FluxLit\napp = FluxLit(title='RF')\n", encoding="utf-8"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)
    called: dict[str, object] = {}

    def stub(target: str, **kwargs: object) -> None:
        called["target"] = target
        called.update(kwargs)

    monkeypatch.setattr("fluxlit.cli.run_unified", stub)
    runner = CliRunner()
    res = runner.invoke(
        app,
        ["dev", "reload_full_app:app", "--reload", "--reload-scope", "full"],
        catch_exceptions=False,
    )
    assert res.exit_code == 0
    assert called.get("reload_scope") == "full"


def test_dev_resolves_target_fluxlit_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "fluxlit.toml").write_text('target = "toml_app:app"\n', encoding="utf-8")
    (tmp_path / "toml_app.py").write_text(
        "from fluxlit import FluxLit\napp = FluxLit(title='T')\n", encoding="utf-8"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)

    called: dict[str, object] = {}

    def fake_run_unified(target: str, **kwargs: object) -> None:
        called["target"] = target
        called.update(kwargs)

    monkeypatch.setattr("fluxlit.cli.run_unified", fake_run_unified)

    runner = CliRunner()
    res = runner.invoke(app, ["dev"], catch_exceptions=False)
    assert res.exit_code == 0
    assert called["target"] == "toml_app:app"


def test_build_refuses_overwrite_without_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    (out / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")

    runner = CliRunner()
    res = runner.invoke(app, ["build", "-o", str(out), "app:app"])
    assert res.exit_code == 1
    assert "--force" in res.stderr or "force" in res.stderr.lower()


def test_build_writes_docker_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    res = runner.invoke(app, ["build", "--force", "-o", str(tmp_path / "out"), "app:app"])
    assert res.exit_code == 0
    df = tmp_path / "out" / "Dockerfile"
    assert df.is_file()
    body = df.read_text(encoding="utf-8")
    assert "fluxlit" in body
    assert 'CMD ["fluxlit", "run", "app:app"]' in body
    assert "USER appuser" in body
    assert "FROM python@sha256:" in body
    assert (tmp_path / "out" / ".dockerignore").is_file()


def test_run_invokes_unified_without_reload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "run_app.py").write_text(
        "from fluxlit import FluxLit\napp = FluxLit(title='Run')\n", encoding="utf-8"
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    called: dict[str, object] = {}

    def stub(target: str, **kwargs: object) -> None:
        called["target"] = target
        called.update(kwargs)

    monkeypatch.setattr("fluxlit.cli.run_unified", stub)
    runner = CliRunner()
    res = runner.invoke(app, ["run", "run_app:app"], catch_exceptions=False)
    assert res.exit_code == 0
    assert called["target"] == "run_app:app"
    assert called["reload"] is False


def test_new_scaffold_writes_app_py(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    res = runner.invoke(app, ["new", "scaffold_demo"], catch_exceptions=False)
    assert res.exit_code == 0
    root = tmp_path / "scaffold_demo"
    app_py = root / "app.py"
    assert app_py.is_file()
    assert "FluxLit" in app_py.read_text(encoding="utf-8")
    toml = root / "fluxlit.toml"
    assert toml.is_file()
    assert 'target = "app:app"' in toml.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("profile", "expected"),
    [
        ("minimal", "FluxLit Demo"),
        ("auth-ready", "Auth-ready Dashboard"),
        ("deploy", "Deployment Dashboard"),
    ],
)
def test_new_scaffold_profiles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    profile: str,
    expected: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    res = runner.invoke(
        app,
        ["new", f"scaffold_{profile}", "--profile", profile],
        catch_exceptions=False,
    )
    assert res.exit_code == 0
    assert profile in res.stdout
    assert expected in (tmp_path / f"scaffold_{profile}" / "app.py").read_text(encoding="utf-8")


def test_new_exits_when_destination_exists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "exists").mkdir()
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    res = runner.invoke(app, ["new", "exists"])
    assert res.exit_code == 1


def test_dev_defaults_come_from_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Validates that `fluxlit dev` uses the app settings for host/port/log_level when omitted.
    """
    module_path = tmp_path / "demo_defaults_app.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n\n"
        "settings = FluxlitSettings(\n"
        "    gateway_host='0.0.0.0',\n"
        "    gateway_port=7777,\n"
        "    log_level='warning',\n"
        ")\n"
        "app = FluxLit(title='Defaults', settings=settings)\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    called = {}

    def fake_run_unified(target: str, **kwargs: object) -> None:
        called["target"] = target
        called.update(kwargs)

    monkeypatch.setattr("fluxlit.cli.run_unified", fake_run_unified)

    runner = CliRunner()
    res = runner.invoke(app, ["dev", "demo_defaults_app:app"])
    assert res.exit_code == 0

    assert called["target"] == "demo_defaults_app:app"
    assert called["host"] == "0.0.0.0"
    assert called["port"] == 7777
    assert called["log_level"] == "warning"


def test_shutdown_no_pidfile_exits_two(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    res = runner.invoke(app, ["shutdown"], catch_exceptions=False)
    assert res.exit_code == 2
    assert "No pid file" in res.stdout


def test_shutdown_exits_zero_on_stale_pid(tmp_path: Path) -> None:
    pid_path = tmp_path / ".fluxlit-dev.pid"
    pid_path.write_text("999999999\n", encoding="ascii")
    runner = CliRunner()
    res = runner.invoke(app, ["shutdown", "--pidfile", str(pid_path)], catch_exceptions=False)
    assert res.exit_code == 0
    assert not pid_path.exists()


def test_shutdown_sends_sigterm_to_recorded_pid(tmp_path: Path) -> None:
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    pid_path = tmp_path / "sub.pid"
    pid_path.write_text(f"{proc.pid}\n", encoding="ascii")
    try:
        runner = CliRunner()
        res = runner.invoke(
            app,
            ["shutdown", "--pidfile", str(pid_path), "--wait", "5"],
            catch_exceptions=False,
        )
        assert res.exit_code == 0
        proc.wait(timeout=15)
        assert proc.returncode is not None
    finally:
        with contextlib.suppress(Exception):
            proc.kill()
            proc.wait(timeout=3)
