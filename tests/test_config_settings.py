"""Robust tests for :class:`~fluxlit.config.FluxlitSettings` env parsing and defaults."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsError

from fluxlit.config import FluxlitSettings


def test_streamlit_run_cli_args_from_json_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLUXLIT_STREAMLIT_RUN_CLI_ARGS", '["--theme.base", "light"]')
    s = FluxlitSettings()
    assert s.streamlit_run_cli_args == ["--theme.base", "light"]


def test_streamlit_page_config_from_json_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "FLUXLIT_STREAMLIT_PAGE_CONFIG",
        '{"layout": "wide", "page_icon": "📊"}',
    )
    s = FluxlitSettings()
    assert s.streamlit_page_config == {"layout": "wide", "page_icon": "📊"}


def test_cors_middleware_kwargs_from_json_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "FLUXLIT_CORS_MIDDLEWARE_KWARGS",
        '{"max_age": 99, "expose_headers": ["X-Custom"]}',
    )
    s = FluxlitSettings()
    assert s.cors_middleware_kwargs == {"max_age": 99, "expose_headers": ["X-Custom"]}


@pytest.mark.parametrize(
    "env_var",
    [
        "FLUXLIT_STREAMLIT_RUN_CLI_ARGS",
        "FLUXLIT_STREAMLIT_PAGE_CONFIG",
        "FLUXLIT_CORS_MIDDLEWARE_KWARGS",
    ],
)
def test_invalid_json_env_raises_settings_error(
    monkeypatch: pytest.MonkeyPatch, env_var: str
) -> None:
    monkeypatch.setenv(env_var, "not-valid-json{")
    with pytest.raises(SettingsError, match="parsing value"):
        FluxlitSettings()


def test_streamlit_run_cli_args_wrong_type_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLUXLIT_STREAMLIT_RUN_CLI_ARGS", '{"oops": "object not list"}')
    with pytest.raises(ValidationError):
        FluxlitSettings()


def test_settings_defaults_are_isolated() -> None:
    """Repeated dict/list defaults must not alias across instances."""
    a = FluxlitSettings()
    b = FluxlitSettings()
    a.streamlit_page_config["k"] = 1
    a.streamlit_run_cli_args.append("--x")
    a.cors_middleware_kwargs["y"] = 2
    assert "k" not in b.streamlit_page_config
    assert b.streamlit_run_cli_args == []
    assert "y" not in b.cors_middleware_kwargs
