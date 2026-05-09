from __future__ import annotations

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


def test_doctor_warnings_only_exit_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module_path = tmp_path / "broken_app.py"
    module_path.write_text("# not a FluxLit instance\napp = 123\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))

    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "broken_app:app", "--warnings-only"])
    assert res.exit_code == 0
    assert "FAIL" in res.stdout


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


def test_build_writes_docker_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    res = runner.invoke(app, ["build", "--force", "-o", str(tmp_path / "out"), "app:app"])
    assert res.exit_code == 0
    df = tmp_path / "out" / "Dockerfile"
    assert df.is_file()
    assert "fluxlit" in df.read_text(encoding="utf-8")
    assert 'CMD ["fluxlit", "run", "app:app"]' in df.read_text(encoding="utf-8")
    assert (tmp_path / "out" / ".dockerignore").is_file()


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
