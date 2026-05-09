from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class FluxlitSettings(BaseSettings):
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
