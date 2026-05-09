from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[import-not-found]


@dataclass
class ProjectConfig:
    """Defaults from ``fluxlit.toml`` or ``pyproject.toml`` ``[tool.fluxlit]``."""

    target: str | None = None
    gateway_host: str | None = None
    gateway_port: int | None = None
    log_level: str | None = None
    api_mount_path: str | None = None
    root_path: str | None = None


_ALLOWED_KEYS = frozenset(
    {
        "target",
        "gateway_host",
        "gateway_port",
        "log_level",
        "api_mount_path",
        "root_path",
    }
)


def _parse_table(raw: dict[str, Any]) -> ProjectConfig:
    kwargs: dict[str, Any] = {}
    for key in _ALLOWED_KEYS:
        if key not in raw:
            continue
        val = raw[key]
        if key == "gateway_port":
            if isinstance(val, bool) or val is None:
                continue
            kwargs[key] = int(val)
        elif isinstance(val, str):
            kwargs[key] = val
    return ProjectConfig(**kwargs)


def load_project_config(cwd: Path | None = None) -> ProjectConfig | None:
    """Load ``fluxlit.toml`` (root keys) or ``[tool.fluxlit]`` from ``pyproject.toml``.

    If both exist, ``fluxlit.toml`` wins.
    """
    root = cwd or Path.cwd()
    fluxlit_path = root / "fluxlit.toml"
    pyproject_path = root / "pyproject.toml"

    if fluxlit_path.is_file():
        data = tomllib.loads(fluxlit_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        return _parse_table(data)

    if pyproject_path.is_file():
        data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        tool = data.get("tool")
        if not isinstance(tool, dict):
            return None
        section = tool.get("fluxlit")
        if not isinstance(section, dict):
            return None
        return _parse_table(section)

    return None


def resolve_target(cli_target: str | None, pc: ProjectConfig | None) -> str:
    if cli_target is not None:
        return cli_target
    if pc and pc.target:
        return pc.target
    return "app:app"


def resolve_binding(
    *,
    cli_host: str | None,
    cli_port: int | None,
    cli_log_level: str | None,
    pc: ProjectConfig | None,
    settings_gateway_host: str,
    settings_gateway_port: int,
    settings_log_level: str,
) -> tuple[str, int, str]:
    """CLI > project file > FluxLit settings (env-backed)."""
    host = cli_host
    if host is None and pc and pc.gateway_host is not None:
        host = pc.gateway_host
    host = host or settings_gateway_host

    port = cli_port
    if port is None and pc and pc.gateway_port is not None:
        port = pc.gateway_port
    port = port or settings_gateway_port

    log_level = cli_log_level
    if log_level is None and pc and pc.log_level is not None:
        log_level = pc.log_level
    log_level = log_level or settings_log_level

    return host, port, log_level
