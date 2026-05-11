from __future__ import annotations

from pathlib import Path

from fluxlit.config import (
    ProjectConfig,
    load_project_config,
    resolve_binding,
    resolve_target,
)


def test_malformed_fluxlit_toml_returns_none(tmp_path: Path) -> None:
    (tmp_path / "fluxlit.toml").write_text("this is not valid toml [[\n", encoding="utf-8")
    assert load_project_config(tmp_path) is None


def test_malformed_pyproject_toml_returns_none(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.fluxlit\n", encoding="utf-8")
    assert load_project_config(tmp_path) is None


def test_load_fluxlit_toml(tmp_path: Path) -> None:
    (tmp_path / "fluxlit.toml").write_text(
        'target = "my:app"\ngateway_port = 9000\nlog_level = "debug"\n',
        encoding="utf-8",
    )
    pc = load_project_config(tmp_path)
    assert pc is not None
    assert pc.target == "my:app"
    assert pc.gateway_port == 9000
    assert pc.log_level == "debug"


def test_fluxlit_toml_wins_over_pyproject(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.fluxlit]\ntarget = "from_py:app"\n',
        encoding="utf-8",
    )
    (tmp_path / "fluxlit.toml").write_text('target = "from_flux:app"\n', encoding="utf-8")
    pc = load_project_config(tmp_path)
    assert pc is not None
    assert pc.target == "from_flux:app"


def test_pyproject_tool_fluxlit(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.fluxlit]\ntarget = "pkg:app"\ngateway_host = "0.0.0.0"\n',
        encoding="utf-8",
    )
    pc = load_project_config(tmp_path)
    assert pc is not None
    assert pc.target == "pkg:app"
    assert pc.gateway_host == "0.0.0.0"


def test_resolve_target_precedence() -> None:
    assert resolve_target("cli:app", ProjectConfig(target="file:app")) == "cli:app"
    assert resolve_target(None, ProjectConfig(target="file:app")) == "file:app"
    assert resolve_target(None, None) == "app:app"


def test_load_project_config_none_when_no_files(tmp_path: Path) -> None:
    assert load_project_config(tmp_path) is None


def test_load_project_config_none_when_tool_fluxlit_missing(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.other]\nx = 1\n", encoding="utf-8")
    assert load_project_config(tmp_path) is None


def test_gateway_port_bool_is_ignored(tmp_path: Path) -> None:
    (tmp_path / "fluxlit.toml").write_text(
        'target = "a:b"\ngateway_port = true\n',
        encoding="utf-8",
    )
    pc = load_project_config(tmp_path)
    assert pc is not None
    assert pc.target == "a:b"
    assert pc.gateway_port is None


def test_resolve_binding_precedence() -> None:
    host, port, log = resolve_binding(
        cli_host=None,
        cli_port=None,
        cli_log_level=None,
        pc=ProjectConfig(gateway_host="0.0.0.0", gateway_port=1111, log_level="warning"),
        settings_gateway_host="127.0.0.1",
        settings_gateway_port=8000,
        settings_log_level="info",
    )
    assert host == "0.0.0.0"
    assert port == 1111
    assert log == "warning"

    host2, port2, log2 = resolve_binding(
        cli_host="10.0.0.1",
        cli_port=2222,
        cli_log_level="error",
        pc=ProjectConfig(gateway_host="0.0.0.0", gateway_port=1111, log_level="warning"),
        settings_gateway_host="127.0.0.1",
        settings_gateway_port=8000,
        settings_log_level="info",
    )
    assert host2 == "10.0.0.1"
    assert port2 == 2222
    assert log2 == "error"
