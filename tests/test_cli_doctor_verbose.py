"""Tests for :mod:`fluxlit.cli_doctor_verbose`."""

from __future__ import annotations

import pytest

from fluxlit import FluxLit
from fluxlit.cli_doctor_verbose import (
    _streamlit_apptest_version_ok,
    build_doctor_verbose_detail,
    format_doctor_verbose_human,
)


def test_build_doctor_verbose_detail_includes_pages_openapi_and_redacted_settings() -> None:
    fl = FluxLit(
        title="DocTest",
        settings=FluxLit().settings.model_copy(update={"jwt_hs256_secret": "s3cr3t"}),
    )

    def home(st, client):  # noqa: ARG001
        pass

    def other(st, client):  # noqa: ARG001
        pass

    fl.page("/", title="Main")(home)
    fl.page("/other")(other)

    detail = build_doctor_verbose_detail(
        fl,
        resolved_target="x:y",
        bind_host="0.0.0.0",
        bind_port=8000,
        pc=None,
    )
    assert detail["resolved_target"] == "x:y"
    assert len(detail["pages"]) == 2
    paths = {p["path"] for p in detail["pages"]}
    assert "/" in paths and "/other" in paths
    assert detail["openapi"]["docs_url"] == "/docs"
    assert detail["settings_redacted"]["jwt_hs256_secret"] == "[REDACTED]"
    assert "internal_api_base_derived" in detail["effective"]
    assert "gateway_proxy" in detail
    assert detail["gateway_proxy"]["upstream_read_timeout_s"] == 120.0


def test_verbose_gateway_proxy_reflects_forward_header_allowlist() -> None:
    from fluxlit.config import FluxlitSettings

    fl = FluxLit(
        settings=FluxlitSettings(
            gateway_forward_client_headers_to_streamlit=["traceparent", "x-request-id"]
        )
    )

    def home(st, client) -> None:  # noqa: ARG001
        pass

    fl.page("/", title="Main")(home)
    detail = build_doctor_verbose_detail(
        fl,
        resolved_target="fwd:fwd",
        bind_host="127.0.0.1",
        bind_port=8000,
        pc=None,
    )
    assert detail["gateway_proxy"]["forward_client_headers_http"] == ["traceparent", "x-request-id"]
    text = "\n".join(format_doctor_verbose_human(detail))
    assert "forward_client_headers_http=['traceparent', 'x-request-id']" in text


def test_format_doctor_verbose_human_import_failed() -> None:
    lines = format_doctor_verbose_human({"resolved_target": "bad:app", "import_failed": True})
    assert "import_failed" in lines[0]
    assert "PYTHONPATH" in "\n".join(lines)


def test_format_doctor_verbose_human_full_detail() -> None:
    fl = FluxLit(title="T")

    def home(st, client):  # noqa: ARG001
        pass

    fl.page("/", title="Main")(home)
    d = build_doctor_verbose_detail(
        fl,
        resolved_target="a:a",
        bind_host="127.0.0.1",
        bind_port=9,
        pc=None,
    )
    text = "\n".join(format_doctor_verbose_human(d))
    assert "resolved_target: a:a" in text
    assert "Hints:" in text
    assert "public_mount_path" in text
    assert "path='/'" in text
    assert "gateway_proxy:" in text


def test_streamlit_apptest_version_ok_handles_bad_version(monkeypatch: pytest.MonkeyPatch) -> None:
    import streamlit as st

    monkeypatch.setattr(st, "__version__", "not-a-version")
    assert _streamlit_apptest_version_ok() is False


def test_openapi_component_returns_none_for_false_url() -> None:
    fl = FluxLit(title="O", fastapi_kwargs={"openapi_url": False, "docs_url": False})
    d = build_doctor_verbose_detail(
        fl,
        resolved_target="o:o",
        bind_host="127.0.0.1",
        bind_port=80,
        pc=None,
    )
    assert d["openapi"]["openapi_url"] is None
    assert d["openapi"]["docs_url"] is None


def test_format_includes_internal_api_env_when_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FLUXLIT_INTERNAL_API_BASE", "http://127.0.0.1:9/api")
    fl = FluxLit(title="E")

    def home(st, client):  # noqa: ARG001
        pass

    fl.page("/", title="")(home)
    d = build_doctor_verbose_detail(
        fl,
        resolved_target="e:e",
        bind_host="127.0.0.1",
        bind_port=9,
        pc=None,
    )
    text = "\n".join(format_doctor_verbose_human(d))
    assert "internal_api_base (env override)" in text


def test_page_handler_string_falls_back_to_qualname_when_module_empty() -> None:
    def handler(st, client) -> None:  # noqa: ARG001
        return None

    handler.__module__ = ""
    handler.__qualname__ = "solo"

    fl = FluxLit(title="H")
    fl.page("/z", title="Z")(handler)
    d = build_doctor_verbose_detail(
        fl,
        resolved_target="h:h",
        bind_host="127.0.0.1",
        bind_port=1,
        pc=None,
    )
    assert d["pages"][0]["handler"] == "solo"
