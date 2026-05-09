from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from fluxlit.cli import app


def test_doctor_prints_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module_path = tmp_path / "demo_cli_app.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n\napp = FluxLit(title='CLI App')\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "demo_cli_app:app"])
    assert res.exit_code == 0
    assert "FluxLit doctor" in res.stdout
    assert "- title: CLI App" in res.stdout
    assert "- api_mount_path:" in res.stdout


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
