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
    - ``trust_proxy`` / ``forwarded_allow_ips`` — Uvicorn proxy trust (e.g. Posit Connect).
    - ``streamlit_public_path`` — optional subpath when ``root_path`` is unset.
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
    streamlit_host: str = Field(
        default="127.0.0.1",
        description="Reserved for future use; Streamlit bind is managed by the runtime.",
    )
    streamlit_port: int = Field(
        default=0,
        description="Reserved for future use; sidecar Streamlit uses an ephemeral port.",
    )
    log_level: str = "info"
    api_mount_path: str = "/api"
    streamlit_public_path: str = Field(
        default="",
        description=(
            "Optional subpath if ``root_path`` is unset; same role for Streamlit "
            "``baseUrlPath``. Prefer ``root_path`` (also sets FastAPI/Uvicorn ASGI root)."
        ),
    )
    root_path: str = Field(
        default="",
        description=(
            "Public URL path prefix when the app is mounted under a subpath "
            "(reverse proxy, Posit Connect / Workbench, etc.). Drives gateway routing, "
            "Streamlit ``server.baseUrlPath``, and ASGI ``root_path`` injected by "
            "``fluxlit run`` (Uvicorn ``root_path`` stays empty so strip-prefix and "
            "full-path proxies do not double the prefix)."
        ),
    )
    trust_proxy: bool = Field(
        default=False,
        description=(
            "If True, enable Uvicorn ``proxy_headers`` so ``X-Forwarded-*`` / scheme "
            "are trusted (typical behind Posit Connect, nginx, or Traefik). "
            "Override with ``fluxlit run --proxy-headers``."
        ),
    )
    forwarded_allow_ips: str | None = Field(
        default=None,
        description=(
            "Uvicorn ``forwarded_allow_ips`` when proxy headers are enabled; "
            "defaults to '*' if unset and the proxy is trusted."
        ),
    )
    enable_request_logging: bool = Field(
        default=False,
        description="Log API requests with X-Request-ID (or generated id) at INFO.",
    )
    enable_security_headers: bool = Field(
        default=False,
        description="If True, add baseline security headers (HSTS, X-Content-Type-Options, etc.).",
    )
    cors_allow_origins: list[str] = Field(
        default_factory=list,
        description=(
            "If non-empty, enable CORS for these origins. Empty list disables CORS middleware."
        ),
    )
    cors_allow_credentials: bool = Field(
        default=False,
        description="Set Access-Control-Allow-Credentials when CORS is enabled.",
    )
    public_base_url: str = Field(
        default="",
        description=(
            "Public origin for OAuth redirects (e.g. https://app.example.com). "
            "If empty, derive from request.url_for / X-Forwarded-* in route handlers."
        ),
    )
    jwt_issuer: str = Field(
        default="",
        description=(
            "JWT ``iss`` claim; used by ``JWTBearer.from_fluxlit_settings`` when validating."
        ),
    )
    jwt_audience: str = Field(
        default="",
        description=(
            "JWT ``aud`` claim (single string); used by ``JWTBearer.from_fluxlit_settings``."
        ),
    )
    jwt_hs256_secret: str = Field(
        default="",
        description="HS256 signing secret for dev/small deployments; leave empty if using JWKS.",
    )
    jwt_jwks_url: str = Field(
        default="",
        description="JWKS URL for RS256 validation; leave empty if using ``jwt_hs256_secret``.",
    )
    jwt_leeway_seconds: int = Field(
        default=0,
        description="Clock skew leeway (seconds) passed to PyJWT when validating tokens.",
    )
    oidc_bff_secret: str = Field(
        default="",
        description=(
            "Secret for first-party JWTs after OIDC callback; "
            "used by ``FluxLit.attach_oidc_login``."
        ),
    )

    def public_mount_path(self) -> str:
        """Browser-visible path prefix (``root_path``, else ``streamlit_public_path``)."""
        r = (self.root_path or "").strip()
        if r:
            return r
        return (self.streamlit_public_path or "").strip()
