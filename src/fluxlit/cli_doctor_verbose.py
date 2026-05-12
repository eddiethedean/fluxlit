"""Verbose snapshot for ``fluxlit doctor --verbose`` / ``--json`` (secrets redacted)."""

from __future__ import annotations

import os
from importlib.util import find_spec
from typing import Any

from fluxlit.app import FluxLit
from fluxlit.config.config_print import project_file_snapshot, redact_fluxlit_settings_dict
from fluxlit.config.project import ProjectConfig
from fluxlit.runtime.import_target import internal_api_base_url

__all__ = [
    "build_doctor_verbose_detail",
    "format_doctor_verbose_human",
    "_streamlit_apptest_version_ok",
]


def _openapi_component(api: object, name: str) -> str | None:
    v = getattr(api, name, None)
    if v is None or v is False:
        return None
    return str(v)


def _streamlit_apptest_version_ok() -> bool:
    try:
        import streamlit as st

        parts = st.__version__.split(".")
        return (int(parts[0]), int(parts[1])) >= (1, 30)
    except Exception:
        return False


def build_doctor_verbose_detail(
    fl: FluxLit[Any],
    *,
    resolved_target: str,
    bind_host: str,
    bind_port: int,
    pc: ProjectConfig | None,
) -> dict[str, Any]:
    """Structured, redacted snapshot for machine or human verbose doctor output."""
    s = fl.settings
    internal_env = os.environ.get("FLUXLIT_INTERNAL_API_BASE", "").strip()
    derived_internal = internal_api_base_url(
        bind_host=bind_host,
        port=bind_port,
        api_mount_path=s.api_mount_path,
    )
    pages: list[dict[str, str]] = []
    for path, title, fn in fl.pages:
        mod = getattr(fn, "__module__", "")
        qn = getattr(fn, "__qualname__", "")
        handler = f"{mod}.{qn}" if mod else qn
        pages.append({"path": path, "title": title, "handler": handler})
    return {
        "resolved_target": resolved_target,
        "pages": pages,
        "settings_redacted": redact_fluxlit_settings_dict(s),
        "effective": {
            "api_mount_path": s.api_mount_path,
            "public_mount_path": s.public_mount_path(),
            "gateway_bind": f"{bind_host}:{bind_port}",
            "internal_api_base_derived": derived_internal,
            "internal_api_base_env": internal_env or None,
            "public_base_url": s.public_base_url.strip() or None,
            "trust_proxy": s.trust_proxy,
            "forwarded_allow_ips": s.forwarded_allow_ips,
            "url_session_query_param": s.url_session_query_param,
            "url_session_fluxlit_tests": bool(os.environ.get("FLUXLIT_TESTS")),
            "url_session_force_in_tests": bool(
                os.environ.get("FLUXLIT_FORCE_URL_SESSION_IN_TESTS")
            ),
            "url_session_disabled": bool(os.environ.get("FLUXLIT_DISABLE_URL_SESSION")),
        },
        "openapi": {
            "openapi_url": _openapi_component(fl.api, "openapi_url"),
            "docs_url": _openapi_component(fl.api, "docs_url"),
            "redoc_url": _openapi_component(fl.api, "redoc_url"),
        },
        "extras": {
            "pyjwt_available": find_spec("jwt") is not None,
            "prometheus_client_available": find_spec("prometheus_client") is not None,
            "streamlit_apptest_version_ok": _streamlit_apptest_version_ok(),
        },
        "streamlit_sidecar": {
            "fluxlit_managed_runtime": True,
            "upstream_file_set": bool(
                os.environ.get("FLUXLIT_STREAMLIT_UPSTREAM_FILE", "").strip()
            ),
            "upstream_url_set": bool(os.environ.get("FLUXLIT_STREAMLIT_UPSTREAM", "").strip()),
        },
        "project_defaults": project_file_snapshot(pc),
    }


def format_doctor_verbose_human(detail: dict[str, Any]) -> list[str]:
    """Fixed-width-friendly lines for stderr/stdout (no secrets beyond redacted settings)."""
    if detail.get("import_failed"):
        return [
            "import_failed: true (see FAIL import_target row above).",
            "Tip: export PYTHONPATH=$(pwd) or pip install -e . from the package root.",
        ]
    lines: list[str] = []
    lines.append(f"resolved_target: {detail['resolved_target']}")
    eff = detail["effective"]
    lines.append(f"gateway_bind (resolved): {eff['gateway_bind']}")
    lines.append(f"api_mount_path: {eff['api_mount_path']!r}")
    lines.append(f"public_mount_path: {eff['public_mount_path']!r}")
    lines.append(f"internal_api_base (derived for Streamlit): {eff['internal_api_base_derived']!r}")
    if eff.get("internal_api_base_env"):
        lines.append(f"internal_api_base (env override): {eff['internal_api_base_env']!r}")
    lines.append(f"public_base_url: {eff['public_base_url']!r}")
    lines.append(f"trust_proxy: {eff['trust_proxy']}")
    lines.append(f"forwarded_allow_ips: {eff['forwarded_allow_ips']!r}")
    lines.append(
        "url_session: "
        f"param={eff['url_session_query_param']!r}; "
        f"FLUXLIT_TESTS={eff['url_session_fluxlit_tests']}; "
        f"FLUXLIT_FORCE_URL_SESSION_IN_TESTS={eff['url_session_force_in_tests']}; "
        f"FLUXLIT_DISABLE_URL_SESSION={eff['url_session_disabled']}"
    )
    oa = detail["openapi"]
    lines.append(
        "openapi: "
        f"openapi_url={oa.get('openapi_url')!r} docs_url={oa.get('docs_url')!r} "
        f"redoc_url={oa.get('redoc_url')!r}"
    )
    ex = detail["extras"]
    lines.append(
        "extras: "
        f"pyjwt={ex['pyjwt_available']} prometheus_client={ex['prometheus_client_available']} "
        f"streamlit_apptest_ok={ex['streamlit_apptest_version_ok']}"
    )
    sc = detail["streamlit_sidecar"]
    lines.append(
        "streamlit_sidecar: "
        f"managed_by_fluxlit_cli={sc['fluxlit_managed_runtime']}; "
        f"FLUXLIT_STREAMLIT_UPSTREAM_FILE set={sc['upstream_file_set']}; "
        f"FLUXLIT_STREAMLIT_UPSTREAM set={sc['upstream_url_set']}"
    )
    pd = detail.get("project_defaults")
    lines.append(f"project_defaults (fluxlit.toml/pyproject): {pd!r}")
    lines.append("pages:")
    for p in detail["pages"]:
        lines.append(f"  - path={p['path']!r} title={p['title']!r} handler={p['handler']}")
    lines.append(
        "settings_redacted: see JSON mode for full object; jwt/oidc secrets are [REDACTED]."
    )
    lines.append("")
    lines.append("Hints:")
    lines.append(
        "  - If Streamlit cannot reach the API: align FLUXLIT_INTERNAL_API_BASE with "
        "internal_api_base_derived (or unset it and let fluxlit run set it)."
    )
    lines.append(
        "  - Behind a subpath proxy: set FLUXLIT_ROOT_PATH and usually FLUXLIT_TRUST_PROXY=1; "
        "see docs/configuration.html and docs/platforms.html."
    )
    lines.append(
        "  - For OAuth redirects: set FLUXLIT_PUBLIC_BASE_URL to the browser-visible URL "
        "(path should match public_mount_path when you use a subpath)."
    )
    return lines
