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


def test_uvicorn_graceful_shutdown_timeout_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLUXLIT_UVICORN_GRACEFUL_SHUTDOWN_TIMEOUT_S", "42.5")
    s = FluxlitSettings()
    assert s.uvicorn_graceful_shutdown_timeout_s == 42.5


def test_gateway_max_proxy_body_bytes_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLUXLIT_GATEWAY_MAX_PROXY_REQUEST_BODY_BYTES", "1048576")
    s = FluxlitSettings()
    assert s.gateway_max_proxy_request_body_bytes == 1048576


def test_public_base_url_uses_legacy_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLUXLIT_PUBLIC_BASE_URL", raising=False)
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://public.example")
    assert FluxlitSettings().public_base_url == "https://public.example"


def test_fluxlit_public_base_url_wins_over_legacy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://legacy.example")
    monkeypatch.setenv("FLUXLIT_PUBLIC_BASE_URL", "https://fluxlit.example")
    assert FluxlitSettings().public_base_url == "https://fluxlit.example"


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


def test_api_mount_path_normalized_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLUXLIT_API_MOUNT_PATH", "api")
    assert FluxlitSettings().api_mount_path == "/api"


def test_api_mount_path_normalized_constructor() -> None:
    assert FluxlitSettings(api_mount_path="v1").api_mount_path == "/v1"
    assert FluxlitSettings(api_mount_path="/x/").api_mount_path == "/x"
