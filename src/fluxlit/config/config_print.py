"""Effective configuration snapshot and validation warnings for CLI ``fluxlit config``."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from fluxlit.config.project import ProjectConfig
from fluxlit.api_mount import normalize_api_mount_path
from fluxlit.runtime.import_target import internal_api_base_url

if TYPE_CHECKING:
    from fluxlit.app import FluxLit as FluxLitType

_SENSITIVE_FIELDS = frozenset(
    {
        "jwt_hs256_secret",
        "oidc_bff_secret",
    }
)

_DOCS_CONFIGURATION = "https://fluxlit.readthedocs.io/en/stable/configuration.html"
_DOCS_SECURITY = "https://fluxlit.readthedocs.io/en/stable/security.html"
_DOCS_PRODUCTION_TLS = "https://fluxlit.readthedocs.io/en/stable/production-tls.html"


def redact_fluxlit_settings_dict(settings: Any) -> dict[str, Any]:
    """Return ``model_dump(mode='json')`` with known secrets replaced."""
    raw: dict[str, Any] = settings.model_dump(mode="json")
    out: dict[str, Any] = {}
    for key, val in raw.items():
        if key in _SENSITIVE_FIELDS and isinstance(val, str) and val.strip():
            out[key] = "[REDACTED]"
            continue
        if key == "cors_middleware_kwargs" and isinstance(val, dict):
            redacted_cors: dict[str, Any] = {}
            for ck, cv in val.items():
                lk = ck.lower()
                if any(s in lk for s in ("secret", "token", "password", "authorization")):
                    redacted_cors[ck] = "[REDACTED]"
                else:
                    redacted_cors[ck] = cv
            out[key] = redacted_cors
            continue
        out[key] = val
    return out


def project_file_snapshot(pc: ProjectConfig | None) -> dict[str, Any] | None:
    """Serialize parsed project defaults (non-None fields only)."""
    if pc is None:
        return None
    data: dict[str, Any] = {}
    for field in (
        "target",
        "gateway_host",
        "gateway_port",
        "log_level",
        "api_mount_path",
        "root_path",
    ):
        val = getattr(pc, field)
        if val is not None:
            data[field] = val
    return data or None


def collect_configuration_warnings(
    *,
    fl: FluxLitType,
    bind_host: str,
    bind_port: int,
) -> list[dict[str, str]]:
    """Return structured warnings (``level`` ``warn`` or ``error``)."""
    warnings: list[dict[str, str]] = []
    s = fl.settings

    internal = os.environ.get("FLUXLIT_INTERNAL_API_BASE", "").strip()
    if internal:
        parsed = urlparse(internal)
        if not parsed.scheme or not parsed.netloc:
            warnings.append(
                {
                    "level": "error",
                    "code": "internal_api_base_invalid",
                    "message": "FLUXLIT_INTERNAL_API_BASE is set but is not a valid absolute URL.",
                    "doc": _DOCS_CONFIGURATION,
                }
            )
        else:
            url_path = (parsed.path or "/").rstrip("/")
            expected = s.api_mount_path.rstrip("/")
            if url_path != expected:
                warnings.append(
                    {
                        "level": "warn",
                        "code": "internal_api_base_path",
                        "message": (
                            f"FLUXLIT_INTERNAL_API_BASE path {url_path!r} should match "
                            f"api_mount_path {expected!r} for Streamlit → API calls."
                        ),
                        "doc": _DOCS_CONFIGURATION,
                    }
                )

    expected_internal = internal_api_base_url(
        bind_host=bind_host,
        port=bind_port,
        api_mount_path=s.api_mount_path,
    )
    if internal and internal.rstrip("/") != expected_internal.rstrip("/"):
        warnings.append(
            {
                "level": "warn",
                "code": "internal_api_base_mismatch",
                "message": (
                    "FLUXLIT_INTERNAL_API_BASE differs from the URL FluxLit would derive "
                    f"from the resolved gateway bind ({expected_internal!r}). "
                    "Mismatch often breaks the injected API client in Streamlit."
                ),
                "doc": _DOCS_CONFIGURATION,
            }
        )

    if s.trust_proxy:
        allow = (s.forwarded_allow_ips or "").strip()
        if not allow or allow == "*":
            warnings.append(
                {
                    "level": "warn",
                    "code": "forwarded_allow_ips_broad",
                    "message": (
                        "trust_proxy is enabled but forwarded_allow_ips is unset or '*' — "
                        "restrict FLUXLIT_FORWARDED_ALLOW_IPS to your reverse proxy in production."
                    ),
                    "doc": _DOCS_PRODUCTION_TLS,
                }
            )

    mount = s.public_mount_path()
    pb = s.public_base_url.strip()
    if pb:
        parsed_public = urlparse(pb)
        if not parsed_public.scheme or not parsed_public.netloc:
            warnings.append(
                {
                    "level": "error",
                    "code": "public_base_url_invalid",
                    "message": "public_base_url is set but is not a valid absolute URL.",
                    "doc": _DOCS_CONFIGURATION,
                }
            )
        else:
            root = mount.rstrip("/")
            public_path = (parsed_public.path or "").rstrip("/")
            if root and public_path and public_path != root:
                warnings.append(
                    {
                        "level": "warn",
                        "code": "public_base_url_path_mismatch",
                        "message": (
                            f"public_base_url path {public_path!r} does not match public mount "
                            f"{root!r} — OAuth redirects and absolute links may be wrong."
                        ),
                        "doc": _DOCS_CONFIGURATION,
                    }
                )
            ap = normalize_api_mount_path(s.api_mount_path)
            if public_path:
                if ap != "/" and ap not in {(public_path + "/").rstrip("/"), public_path}:
                    if not public_path.endswith(ap.rstrip("/")):
                        warnings.append(
                            {
                                "level": "warn",
                                "code": "public_base_url_missing_api_prefix",
                                "message": (
                                    "public_base_url path may omit the API mount — "
                                    "browser-visible OpenAPI/docs URLs are usually under "
                                    "api_mount_path."
                                ),
                                "doc": _DOCS_CONFIGURATION,
                            }
                        )

    if mount and not pb:
        warnings.append(
            {
                "level": "warn",
                "code": "oauth_public_base_url",
                "message": (
                    "A subpath is configured but public_base_url is empty — set "
                    "FLUXLIT_PUBLIC_BASE_URL for correct OAuth redirect_uri behind a reverse proxy."
                ),
                "doc": _DOCS_CONFIGURATION,
            }
        )

    if mount and not s.trust_proxy:
        warnings.append(
            {
                "level": "warn",
                "code": "subpath_without_trust_proxy",
                "message": (
                    "subpath/root_path is set but trust_proxy is false — behind Posit Connect "
                    "or nginx set FLUXLIT_TRUST_PROXY=1 (or pass --proxy-headers) so forwarded "
                    "host/proto are visible to the app."
                ),
                "doc": _DOCS_PRODUCTION_TLS,
            }
        )

    cors_on = bool(s.cors_allow_origins)
    if cors_on and not s.enable_security_headers:
        warnings.append(
            {
                "level": "warn",
                "code": "cors_without_security_headers",
                "message": (
                    "CORS is enabled but security headers are off — consider "
                    "FLUXLIT_ENABLE_SECURITY_HEADERS=1 (review CSP/HSTS vs Streamlit/WebSockets)."
                ),
                "doc": _DOCS_SECURITY,
            }
        )

    if s.enable_security_headers and s.streamlit_page_config.get("csp"):
        warnings.append(
            {
                "level": "warn",
                "code": "csp_with_security_headers",
                "message": (
                    "Both enable_security_headers and streamlit_page_config CSP hints are set — "
                    "verify they do not break Streamlit websockets or embedded assets."
                ),
                "doc": _DOCS_SECURITY,
            }
        )

    return warnings


def project_file_mount_warnings(pc: ProjectConfig | None) -> list[dict[str, str]]:
    """Warn when project file lists mount keys not merged into FluxLit settings."""
    if pc is None:
        return []
    if pc.api_mount_path is None and pc.root_path is None:
        return []
    return [
        {
            "level": "warn",
            "code": "project_file_mount_not_merged",
            "message": (
                "fluxlit.toml / pyproject [tool.fluxlit] includes api_mount_path or root_path. "
                "These keys are parsed for tooling but are not applied to FluxLit.settings — "
                "set FLUXLIT_API_MOUNT_PATH / FLUXLIT_ROOT_PATH (or pass FluxlitSettings(...)) "
                "so the running app matches the project file."
            ),
            "doc": _DOCS_CONFIGURATION,
        }
    ]


def build_config_payload(
    *,
    target: str,
    bind_host: str,
    bind_port: int,
    log_level: str,
    pc: ProjectConfig | None,
    fl: FluxLitType,
) -> dict[str, Any]:
    """Structured payload for ``fluxlit config`` / ``--json``."""
    derived_internal = internal_api_base_url(
        bind_host=bind_host,
        port=bind_port,
        api_mount_path=fl.settings.api_mount_path,
    )
    ambient_internal = os.environ.get("FLUXLIT_INTERNAL_API_BASE", "").strip()
    warnings = [
        *project_file_mount_warnings(pc),
        *collect_configuration_warnings(fl=fl, bind_host=bind_host, bind_port=bind_port),
    ]
    return {
        "target": target,
        "binding": {"host": bind_host, "port": bind_port, "log_level": log_level},
        "project_file": project_file_snapshot(pc),
        "computed": {
            "public_mount_path": fl.settings.public_mount_path(),
            "derived_internal_api_base": derived_internal,
            "ambient_internal_api_base": ambient_internal or None,
        },
        "settings": redact_fluxlit_settings_dict(fl.settings),
        "warnings": warnings,
    }


__all__ = [
    "build_config_payload",
    "collect_configuration_warnings",
    "project_file_mount_warnings",
    "project_file_snapshot",
    "redact_fluxlit_settings_dict",
]
