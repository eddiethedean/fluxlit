"""Configuration: settings, project file defaults, and JSON value typing."""

from fluxlit.config.json_types import JsonValue
from fluxlit.config.project import (
    ProjectConfig,
    load_project_config,
    resolve_binding,
    resolve_target,
)
from fluxlit.config.settings import FluxlitSettings

__all__ = [
    "FluxlitSettings",
    "JsonValue",
    "ProjectConfig",
    "load_project_config",
    "resolve_binding",
    "resolve_target",
]
