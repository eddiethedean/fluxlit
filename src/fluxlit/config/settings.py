"""Application settings loaded from environment and optional ``.env`` file."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any

from typing_extensions import Self
from urllib.parse import urlparse

from pydantic import Field, PrivateAttr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from fluxlit.api_mount import normalize_api_mount_path
from fluxlit.config.json_types import JsonValue


def _parse_raw_gateway_forward_env(env_raw: str) -> list[str]:
    """Parse ``FLUXLIT_GATEWAY_FORWARD_CLIENT_HEADERS_TO_STREAMLIT`` for reject diagnostics."""
    text = env_raw.strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
        return []
    return [p.strip() for p in text.split(",") if p.strip()]


class FluxlitSettings(BaseSettings):
    """Runtime configuration for FluxLit, CLI defaults, and FastAPI construction.

    Values are read from environment variables prefixed with ``FLUXLIT_`` and from a
    ``.env`` file in the working directory if present. Unknown env keys are ignored.

    CLI commands such as ``fluxlit dev`` merge these with ``fluxlit.toml`` / ``pyproject``
    ``[tool.fluxlit]`` and explicit flags; see :mod:`fluxlit.config.project` for precedence.

    Key fields:

    - ``title`` — FastAPI / UX title.
    - ``gateway_host`` / ``gateway_port`` — default bind address for Uvicorn.
    - ``api_mount_path`` — public URL prefix for the API (default ``/api``).
    - ``root_path`` — ASGI root when behind a reverse proxy.
    - ``enable_request_logging`` — per-request INFO logs on the FastAPI app.
    - ``enable_gateway_access_log`` — per-request INFO logs on the gateway (structured extras).
    - ``trust_proxy`` / ``forwarded_allow_ips`` — Uvicorn proxy trust (e.g. Posit Connect).
    - ``streamlit_public_path`` — optional subpath when ``root_path`` is unset.
    - ``streamlit_run_cli_args`` — extra ``streamlit run`` CLI tokens (JSON list in env).
    - ``streamlit_page_config`` — keys forwarded to ``st.set_page_config`` (JSON object in env).
    - ``cors_middleware_kwargs`` — extra kwargs for ``CORSMiddleware`` when CORS is enabled.
    - ``experimental_yield_pages`` / ``async_page_depends`` — **experimental**; semantics
      and promotion criteria are in ``docs/support-matrix`` (Experimental ``FluxlitSettings``).
    """

    model_config = SettingsConfigDict(
        env_prefix="FLUXLIT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    _rejected_forward_headers: tuple[str, ...] = PrivateAttr(default_factory=tuple)

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

    @field_validator("api_mount_path", mode="after")
    @classmethod
    def _normalize_api_mount_path_field(cls, v: str) -> str:
        return normalize_api_mount_path(v)

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
    enable_gateway_access_log: bool = Field(
        default=False,
        description=(
            "Log each gateway request at INFO with structured fields "
            "(fluxlit_dispatch, path, redacted query); default is DEBUG only."
        ),
    )
    debug: bool = Field(
        default=False,
        description=(
            "When true (``FLUXLIT_DEBUG=1`` or ``fluxlit dev/run --debug``), enable "
            "gateway access logs, API request logging, bump default log level to ``debug``, "
            "expose ``GET /__fluxlit/debug`` on the gateway, and propagate request ids from "
            ":meth:`fluxlit.app.FluxLit.get_client` where applicable. Do not enable in production."
        ),
    )
    url_session_query_param: str = Field(
        default="fluxlit_sid",
        description=(
            "Query parameter name used by :mod:`fluxlit.url_session` helpers for "
            "URL-bound session continuity. The gateway access log redacts this key's "
            "value (and the default ``fluxlit_sid``) in the structured ``query`` field."
        ),
    )
    enable_gateway_prometheus_metrics: bool = Field(
        default=False,
        description=(
            "If True, expose Prometheus metrics on the gateway ASGI app and increment "
            "RED-style counters/histograms. Requires ``prometheus-client`` "
            "(``pip install 'fluxlit[metrics]'`` or add to your image)."
        ),
    )
    gateway_prometheus_metrics_path: str = Field(
        default="/__fluxlit/metrics",
        description=(
            "HTTP GET path (after ``root_path`` strip) for Prometheus text exposition. "
            "Must not start with ``api_mount_path`` or you will shadow API routes."
        ),
    )
    gateway_upstream_connect_timeout_s: float = Field(
        default=30.0,
        ge=0.0,
        description="``httpx`` connect timeout (seconds) for gateway → Streamlit HTTP proxy.",
    )
    gateway_upstream_read_timeout_s: float = Field(
        default=120.0,
        ge=0.0,
        description="``httpx`` read timeout (seconds) for gateway → Streamlit HTTP proxy.",
    )
    gateway_max_proxy_request_body_bytes: int = Field(
        default=0,
        ge=0,
        description=(
            "Max incoming request body bytes proxied to Streamlit; ``0`` means unlimited. "
            "When exceeded, the gateway responds with **413**. "
            "Upstream **responses** are fully buffered in the gateway process (see gateway proxy "
            "notes); tune Streamlit/file responses separately if memory is a concern."
        ),
    )
    gateway_max_concurrent_upstream_http: int = Field(
        default=0,
        ge=0,
        description=(
            "Max concurrent in-flight HTTP proxy requests to Streamlit; ``0`` means no limit."
        ),
    )
    gateway_httpx_max_connections: int = Field(
        default=0,
        ge=0,
        description=(
            "``httpx.Limits.max_connections`` for the shared gateway client; ``0`` uses "
            "httpx defaults."
        ),
    )
    gateway_httpx_max_keepalive_connections: int = Field(
        default=0,
        ge=0,
        description=(
            "``httpx.Limits.max_keepalive_connections`` when ``gateway_httpx_max_connections`` "
            "is set; ``0`` lets httpx derive a value."
        ),
    )
    gateway_ws_open_timeout_s: float = Field(
        default=30.0,
        ge=0.0,
        description="WebSocket client ``open_timeout`` (seconds) to the Streamlit upstream.",
    )
    gateway_ws_ping_interval_s: float | None = Field(
        default=None,
        description=(
            "Optional ``ping_interval`` for the upstream WebSocket (library default if unset)."
        ),
    )
    gateway_ws_ping_timeout_s: float | None = Field(
        default=None,
        description="Optional ``ping_timeout`` for the upstream WebSocket.",
    )
    gateway_ws_close_timeout_s: float | None = Field(
        default=None,
        description="Optional ``close_timeout`` for the upstream WebSocket.",
    )
    gateway_ws_max_message_bytes: int | None = Field(
        default=None,
        description=(
            "Optional ``max_size`` (bytes) for upstream WebSocket frames; ``None`` is unlimited."
        ),
    )
    gateway_forward_client_headers_to_streamlit: list[str] = Field(
        default_factory=list,
        description=(
            "Optional allowlist of HTTP header names (case-insensitive) **merged** from "
            "the raw browser request onto the gateway → Streamlit **HTTP** hop (after "
            "``filter_request_headers`` and synthetic forwarding headers). Does **not** "
            "strip other client headers already copied by the proxy. Credential and "
            "hop-by-hop names are rejected from the allowlist. Empty list skips this "
            "merge only. WebSocket handshakes ignore this setting."
        ),
    )

    @field_validator("gateway_forward_client_headers_to_streamlit", mode="before")
    @classmethod
    def _coerce_forward_header_list(cls, v: object) -> list[str]:
        if v is None or v == "":
            return []
        if isinstance(v, str):
            return [p.strip() for p in v.split(",") if p.strip()]
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        return []

    @field_validator("gateway_forward_client_headers_to_streamlit", mode="after")
    @classmethod
    def _validate_forward_header_list(cls, v: list[str]) -> list[str]:
        from fluxlit.gateway.forward_headers import normalize_gateway_forward_header_allowlist

        norm = normalize_gateway_forward_header_allowlist(v)
        if len(norm) > 32:
            msg = "gateway_forward_client_headers_to_streamlit supports at most 32 names"
            raise ValueError(msg)
        return sorted(norm)

    uvicorn_graceful_shutdown_timeout_s: float | None = Field(
        default=None,
        ge=0.0,
        description=(
            "If set, passed to Uvicorn ``timeout_graceful_shutdown`` (align with Kubernetes "
            "``terminationGracePeriodSeconds`` minus ``preStop`` work)."
        ),
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
    cors_middleware_kwargs: dict[str, JsonValue] = Field(
        default_factory=dict,
        description=(
            "Additional keyword arguments for Starlette ``CORSMiddleware`` when "
            "``cors_allow_origins`` is non-empty (e.g. ``expose_headers``, ``max_age``). "
            "Do not pass ``allow_origins``, ``allow_credentials``, ``allow_methods``, or "
            "``allow_headers`` here (FluxLit sets those); such keys are ignored."
        ),
    )
    streamlit_run_cli_args: list[str] = Field(
        default_factory=list,
        description=(
            "Extra CLI arguments appended after FluxLit’s built-in ``streamlit run`` flags "
            "(later arguments override earlier ones per Streamlit CLI rules). Must not set "
            "``--server.port``, ``--server.address``, or ``--server.baseUrlPath`` (FluxLit "
            "controls the sidecar bind and public mount)."
        ),
    )
    streamlit_page_config: dict[str, JsonValue] = Field(
        default_factory=dict,
        description=(
            "Keyword arguments merged into ``streamlit.set_page_config`` after "
            "``page_title`` (defaulting to :attr:`title`). Supported keys include "
            "``page_icon``, ``layout``, ``initial_sidebar_state``, ``menu_items``; "
            "unknown keys are ignored."
        ),
    )
    public_base_url: str = Field(
        default="",
        description=(
            "Public origin for OAuth redirects (e.g. https://app.example.com). "
            "If empty, derive from request.url_for / X-Forwarded-* in route handlers."
        ),
    )
    strict_public_base_url: bool = Field(
        default=False,
        description=(
            "If True, deployment diagnostics should fail when PUBLIC_BASE_URL and "
            "FLUXLIT_PUBLIC_BASE_URL are both set to different values."
        ),
    )
    strict_page_signatures: bool = Field(
        default=False,
        description=(
            "If True, :meth:`fluxlit.app.FluxLit.page` rejects Streamlit handlers whose "
            "parameters are not recognized injectables (``st``, ``client``, typed deps, "
            "``Depends``, etc.)."
        ),
    )
    strict_startup: bool = Field(
        default=False,
        description=(
            "If True, reject settings combinations at model construction that "
            "``fluxlit doctor --strict`` would flag (broad ``forwarded_allow_ips`` with "
            "``trust_proxy``, unlimited proxied body with ``trust_proxy``, subpath without "
            "``public_base_url`` / ``trust_proxy``, rejected gateway forward-header names, "
            "``public_base_url`` path vs mount mismatch). Env: ``FLUXLIT_STRICT_STARTUP``."
        ),
    )
    experimental_yield_pages: bool = Field(
        default=False,
        description=(
            "When True (``FLUXLIT_EXPERIMENTAL_YIELD_PAGES=1``), generator page handlers "
            "run ``next()`` twice per script execution (experimental)."
        ),
    )
    async_page_depends: bool = Field(
        default=False,
        description=(
            "When True (``FLUXLIT_ASYNC_PAGE_DEPENDS=1``), :class:`~fluxlit.pages.di.Depends` "
            "callables may be ``async def`` or return awaitables."
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

    @model_validator(mode="wrap")
    @classmethod
    def _capture_forward_header_rejects(cls, data: Any, handler: Callable[[Any], Any]) -> Any:
        """Record header names users requested that are rejected (never forwarded)."""
        raw_list: list[str] = []
        keyed = isinstance(data, dict) and "gateway_forward_client_headers_to_streamlit" in data
        if keyed:
            raw = data["gateway_forward_client_headers_to_streamlit"]
            if isinstance(raw, str):
                raw_list = [p.strip() for p in raw.split(",") if p.strip()]
            elif isinstance(raw, list):
                raw_list = [str(x).strip() for x in raw if str(x).strip()]
        if not raw_list and not keyed:
            raw_list = _parse_raw_gateway_forward_env(
                os.environ.get("FLUXLIT_GATEWAY_FORWARD_CLIENT_HEADERS_TO_STREAMLIT", "")
            )
        model = handler(data)
        if isinstance(model, FluxlitSettings):
            from fluxlit.gateway.forward_headers import rejected_gateway_forward_header_allowlist

            model._rejected_forward_headers = rejected_gateway_forward_header_allowlist(raw_list)
        return model

    @model_validator(mode="after")
    def _apply_legacy_public_base_url(self) -> Self:
        """Match ``PUBLIC_BASE_URL`` fallback after field validation (see prior ``__init__``)."""
        legacy = os.environ.get("PUBLIC_BASE_URL", "").strip()
        namespaced = os.environ.get("FLUXLIT_PUBLIC_BASE_URL", "").strip()
        if legacy and not namespaced and not self.public_base_url.strip():
            self.public_base_url = legacy
        return self

    @model_validator(mode="after")
    def _strict_startup_validate(self) -> Self:
        if not self.strict_startup:
            return self
        if self.trust_proxy:
            allow = (self.forwarded_allow_ips or "").strip()
            if not allow or allow == "*":
                msg = (
                    "strict_startup: set FLUXLIT_FORWARDED_ALLOW_IPS to a non-wildcard value "
                    "when FLUXLIT_TRUST_PROXY is enabled"
                )
                raise ValueError(msg)
            if self.gateway_max_proxy_request_body_bytes == 0:
                msg = (
                    "strict_startup: set FLUXLIT_GATEWAY_MAX_PROXY_REQUEST_BODY_BYTES when "
                    "FLUXLIT_TRUST_PROXY is enabled (unlimited proxied body is rejected)"
                )
                raise ValueError(msg)
        mount = self.public_mount_path()
        if mount and not self.public_base_url.strip():
            msg = (
                "strict_startup: set FLUXLIT_PUBLIC_BASE_URL when using a subpath "
                "(root_path / streamlit_public_path)"
            )
            raise ValueError(msg)
        if mount and not self.trust_proxy:
            msg = (
                "strict_startup: enable FLUXLIT_TRUST_PROXY (or pass --proxy-headers) when "
                "using a subpath behind a reverse proxy"
            )
            raise ValueError(msg)
        rejected = tuple(getattr(self, "_rejected_forward_headers", ()))
        if rejected:
            msg = f"strict_startup: remove rejected gateway forward header names: {list(rejected)}"
            raise ValueError(msg)
        pb = self.public_base_url.strip()
        if pb:
            parsed = urlparse(pb)
            root = mount.rstrip("/")
            public_path = (parsed.path or "").rstrip("/")
            if root and public_path and public_path != root:
                msg = (
                    "strict_startup: public_base_url path does not match public mount "
                    f"({public_path!r} vs {root!r})"
                )
                raise ValueError(msg)
        return self

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)

    def public_mount_path(self) -> str:
        """Browser-visible path prefix (``root_path``, else ``streamlit_public_path``)."""
        r = (self.root_path or "").strip()
        if r:
            return r
        return (self.streamlit_public_path or "").strip()


__all__ = ["FluxlitSettings"]
