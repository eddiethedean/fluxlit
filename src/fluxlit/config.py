"""Application settings loaded from environment and optional ``.env`` file."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class FluxlitSettings(BaseSettings):
    """Runtime configuration for FluxLit, CLI defaults, and FastAPI construction.

    Values are read from environment variables prefixed with ``FLUXLIT_`` and from a
    ``.env`` file in the working directory if present. Unknown env keys are ignored.

    CLI commands such as ``fluxlit dev`` merge these with ``fluxlit.toml`` / ``pyproject``
    ``[tool.fluxlit]`` and explicit flags; see :mod:`fluxlit.project_config` for precedence.

    Key fields:

    - ``title`` — FastAPI / UX title.
    - ``gateway_host`` / ``gateway_port`` — default bind address for Uvicorn.
    - ``api_mount_path`` — public URL prefix for the API (default ``/api``).
    - ``root_path`` — ASGI root when behind a reverse proxy.
    - ``enable_request_logging`` — per-request INFO logs on the FastAPI app.
    """

    model_config = SettingsConfigDict(
        env_prefix="FLUXLIT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    title: str = "FluxLit"
    gateway_host: str = "127.0.0.1"
    gateway_port: int = 8000
    streamlit_host: str = "127.0.0.1"
    streamlit_port: int = 0
    log_level: str = "info"
    api_mount_path: str = "/api"
    streamlit_public_path: str = ""
    root_path: str = Field(
        default="",
        description="ASGI root path when served behind a reverse proxy (e.g. /myapp).",
    )
    enable_request_logging: bool = Field(
        default=False,
        description="Log API requests with X-Request-ID (or generated id) at INFO.",
    )
