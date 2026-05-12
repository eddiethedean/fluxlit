from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from fluxlit import FluxLit
from fluxlit.cli import app
from fluxlit.config import FluxlitSettings, ProjectConfig
from fluxlit.config.config_print import (
    build_config_payload,
    collect_configuration_warnings,
    project_file_mount_warnings,
    redact_fluxlit_settings_dict,
)


def test_redact_fluxlit_settings_masks_secrets() -> None:
    s = FluxlitSettings(
        jwt_hs256_secret="super-secret",
        oidc_bff_secret="bff-secret",
    )
    d = redact_fluxlit_settings_dict(s)
    assert d["jwt_hs256_secret"] == "[REDACTED]"
    assert d["oidc_bff_secret"] == "[REDACTED]"
    assert d["title"] == "FluxLit"


def test_redact_fluxlit_settings_cors_kwargs() -> None:
    s = FluxlitSettings(
        cors_middleware_kwargs={"api_secret_header": "x", "expose_headers": ["X-Request-ID"]},
    )
    d = redact_fluxlit_settings_dict(s)
    assert d["cors_middleware_kwargs"]["api_secret_header"] == "[REDACTED]"
    assert d["cors_middleware_kwargs"]["expose_headers"] == ["X-Request-ID"]


def test_project_file_mount_warnings_present() -> None:
    pc = ProjectConfig(target="a:b", api_mount_path="/v2")
    w = project_file_mount_warnings(pc)
    assert len(w) == 1
    assert w[0]["code"] == "project_file_mount_not_merged"


def test_project_file_mount_warnings_absent() -> None:
    assert project_file_mount_warnings(None) == []
    assert project_file_mount_warnings(ProjectConfig(target="a:b")) == []


def test_collect_warnings_forwarded_allow_ips_broad() -> None:
    fl = FluxLit(settings=FluxlitSettings(trust_proxy=True, forwarded_allow_ips="*"))
    w = collect_configuration_warnings(fl=fl, bind_host="127.0.0.1", bind_port=8000)
    assert any(x["code"] == "forwarded_allow_ips_broad" for x in w)


def test_collect_warnings_internal_api_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    fl = FluxLit(settings=FluxlitSettings(api_mount_path="/api"))
    monkeypatch.setenv("FLUXLIT_INTERNAL_API_BASE", "not-a-url")
    w = collect_configuration_warnings(fl=fl, bind_host="127.0.0.1", bind_port=8000)
    assert any(x["code"] == "internal_api_base_invalid" for x in w)
    monkeypatch.delenv("FLUXLIT_INTERNAL_API_BASE", raising=False)


def test_collect_warnings_internal_path_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    fl = FluxLit(settings=FluxlitSettings(api_mount_path="/api"))
    monkeypatch.setenv("FLUXLIT_INTERNAL_API_BASE", "http://127.0.0.1:8000/wrong")
    w = collect_configuration_warnings(fl=fl, bind_host="127.0.0.1", bind_port=8000)
    assert any(x["code"] == "internal_api_base_path" for x in w)
    monkeypatch.delenv("FLUXLIT_INTERNAL_API_BASE", raising=False)


def test_collect_warnings_internal_base_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    fl = FluxLit(settings=FluxlitSettings(api_mount_path="/api"))
    monkeypatch.setenv("FLUXLIT_INTERNAL_API_BASE", "http://127.0.0.1:9999/api")
    w = collect_configuration_warnings(fl=fl, bind_host="127.0.0.1", bind_port=8000)
    assert any(x["code"] == "internal_api_base_mismatch" for x in w)
    monkeypatch.delenv("FLUXLIT_INTERNAL_API_BASE", raising=False)


def test_collect_warnings_public_base_invalid() -> None:
    fl = FluxLit(settings=FluxlitSettings(public_base_url="not-a-url"))
    w = collect_configuration_warnings(fl=fl, bind_host="127.0.0.1", bind_port=8000)
    assert any(x["code"] == "public_base_url_invalid" for x in w)


def test_collect_warnings_public_base_path_mismatch() -> None:
    fl = FluxLit(
        settings=FluxlitSettings(
            root_path="/apps/foo",
            public_base_url="https://example.com/apps/bar",
        )
    )
    w = collect_configuration_warnings(fl=fl, bind_host="127.0.0.1", bind_port=8000)
    assert any(x["code"] == "public_base_url_path_mismatch" for x in w)


def test_collect_warnings_public_base_missing_api_prefix() -> None:
    fl = FluxLit(
        settings=FluxlitSettings(
            public_base_url="https://example.com/prefix",
        )
    )
    w = collect_configuration_warnings(fl=fl, bind_host="127.0.0.1", bind_port=8000)
    assert any(x["code"] == "public_base_url_missing_api_prefix" for x in w)


def test_collect_warnings_oauth_public_base() -> None:
    fl = FluxLit(settings=FluxlitSettings(root_path="/app"))
    w = collect_configuration_warnings(fl=fl, bind_host="127.0.0.1", bind_port=8000)
    assert any(x["code"] == "oauth_public_base_url" for x in w)


def test_collect_warnings_subpath_without_trust_proxy() -> None:
    fl = FluxLit(settings=FluxlitSettings(root_path="/app", trust_proxy=False))
    w = collect_configuration_warnings(fl=fl, bind_host="127.0.0.1", bind_port=8000)
    assert any(x["code"] == "subpath_without_trust_proxy" for x in w)


def test_collect_warnings_cors_without_security_headers() -> None:
    fl = FluxLit(
        settings=FluxlitSettings(
            cors_allow_origins=["https://a.example"],
            enable_security_headers=False,
        )
    )
    w = collect_configuration_warnings(fl=fl, bind_host="127.0.0.1", bind_port=8000)
    assert any(x["code"] == "cors_without_security_headers" for x in w)


def test_collect_warnings_csp_with_security_headers() -> None:
    fl = FluxLit(
        settings=FluxlitSettings(
            enable_security_headers=True,
            streamlit_page_config={"csp": "default-src 'self'"},
        )
    )
    w = collect_configuration_warnings(fl=fl, bind_host="127.0.0.1", bind_port=8000)
    assert any(x["code"] == "csp_with_security_headers" for x in w)


def test_build_config_payload_merges_project_warnings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "fluxlit.toml").write_text(
        'target = "cfg_pf_app:app"\napi_mount_path = "/v2"\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    (tmp_path / "cfg_pf_app.py").write_text(
        "from fluxlit import FluxLit\n\napp = FluxLit()\n",
        encoding="utf-8",
    )
    from fluxlit.config import load_project_config

    pc = load_project_config()
    assert pc is not None
    fl = FluxLit()
    payload = build_config_payload(
        target="cfg_pf_app:app",
        bind_host="127.0.0.1",
        bind_port=8000,
        log_level="info",
        pc=pc,
        fl=fl,
    )
    assert payload["project_file"]["api_mount_path"] == "/v2"
    assert any(w["code"] == "project_file_mount_not_merged" for w in payload["warnings"])


def test_config_cli_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.syspath_prepend(str(tmp_path))
    (tmp_path / "cfg_cli_app.py").write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n\n"
        "app = FluxLit(settings=FluxlitSettings(gateway_port=59231, jwt_hs256_secret='x'))\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    res = runner.invoke(app, ["config", "cfg_cli_app:app", "--json"])
    assert res.exit_code == 0
    payload = json.loads(res.stdout)
    assert payload["target"] == "cfg_cli_app:app"
    assert payload["settings"]["jwt_hs256_secret"] == "[REDACTED]"
    assert "warnings" in payload


def test_config_cli_human(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.syspath_prepend(str(tmp_path))
    (tmp_path / "cfg_human_app.py").write_text(
        "from fluxlit import FluxLit\n\napp = FluxLit()\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    res = runner.invoke(app, ["config", "cfg_human_app:app"])
    assert res.exit_code == 0
    assert "FluxLit effective configuration" in res.stdout
    assert "Settings (redacted, JSON):" in res.stdout


def test_config_cli_strict_exits_on_warn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.syspath_prepend(str(tmp_path))
    (tmp_path / "cfg_strict_app.py").write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n\n"
        "app = FluxLit(settings=FluxlitSettings(trust_proxy=True, forwarded_allow_ips='*'))\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    res = runner.invoke(app, ["config", "cfg_strict_app:app", "--json", "--strict"])
    assert res.exit_code == 1
    payload = json.loads(res.stdout)
    assert any(w["code"] == "forwarded_allow_ips_broad" for w in payload["warnings"])


def test_config_cli_strict_fails_on_combined_0_11_warnings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.syspath_prepend(str(tmp_path))
    (tmp_path / "cfg_strict_011.py").write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n\n"
        "app = FluxLit(settings=FluxlitSettings(\n"
        "    trust_proxy=True,\n"
        "    gateway_max_proxy_request_body_bytes=0,\n"
        "    forwarded_allow_ips='*',\n"
        "    gateway_forward_client_headers_to_streamlit=['Authorization'],\n"
        "))\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    res = runner.invoke(app, ["config", "cfg_strict_011:app", "--json", "--strict"])
    assert res.exit_code == 1
    payload = json.loads(res.stdout)
    codes = {w["code"] for w in payload["warnings"]}
    assert "forwarded_allow_ips_broad" in codes
    assert "gateway_forward_blocked_names" in codes
    assert "gateway_max_body_unlimited_trust_proxy" in codes


def test_config_cli_human_shows_ambient_internal_api_base(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.syspath_prepend(str(tmp_path))
    (tmp_path / "cfg_ambient_app.py").write_text(
        "from fluxlit import FluxLit\n\napp = FluxLit()\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FLUXLIT_INTERNAL_API_BASE", "http://127.0.0.1:8000/api")
    runner = CliRunner()
    res = runner.invoke(app, ["config", "cfg_ambient_app:app"])
    monkeypatch.delenv("FLUXLIT_INTERNAL_API_BASE", raising=False)
    assert res.exit_code == 0
    assert "FLUXLIT_INTERNAL_API_BASE:" in res.stdout


def test_config_cli_human_shows_project_file_and_warning_docs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "fluxlit.toml").write_text(
        'target = "cfg_human2_app:app"\napi_mount_path = "/v2"\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    (tmp_path / "cfg_human2_app.py").write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n\n"
        "app = FluxLit(settings=FluxlitSettings(trust_proxy=True, forwarded_allow_ips='*'))\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    res = runner.invoke(app, ["config", "cfg_human2_app:app"])
    assert res.exit_code == 0
    assert "project_file:" in res.stdout
    assert "Warnings:" in res.stdout
    assert "Docs: https://" in res.stdout


def test_config_cli_errors_on_invalid_public_base_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.syspath_prepend(str(tmp_path))
    (tmp_path / "cfg_bad_pub.py").write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n\n"
        "app = FluxLit(settings=FluxlitSettings(public_base_url='not-a-url'))\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    res = runner.invoke(app, ["config", "cfg_bad_pub:app", "--json"])
    assert res.exit_code == 1


def test_collect_warnings_gateway_forward_blocked_names() -> None:
    fl = FluxLit(
        settings=FluxlitSettings(
            gateway_forward_client_headers_to_streamlit=["Authorization", "traceparent"]
        )
    )
    w = collect_configuration_warnings(fl=fl, bind_host="127.0.0.1", bind_port=8000)
    assert any(x["code"] == "gateway_forward_blocked_names" for x in w)
    assert any(
        "authorization" in x["message"].lower()
        for x in w
        if x["code"] == "gateway_forward_blocked_names"
    )


def test_collect_warnings_gateway_max_body_unlimited_with_trust_proxy() -> None:
    fl = FluxLit(settings=FluxlitSettings(trust_proxy=True, gateway_max_proxy_request_body_bytes=0))
    w = collect_configuration_warnings(fl=fl, bind_host="127.0.0.1", bind_port=8000)
    assert any(x["code"] == "gateway_max_body_unlimited_trust_proxy" for x in w)


def test_collect_warnings_multiple_rejected_forward_names_sorted_in_message() -> None:
    fl = FluxLit(
        settings=FluxlitSettings(
            gateway_forward_client_headers_to_streamlit=[
                "Cookie",
                "Authorization",
                "traceparent",
            ]
        )
    )
    w = collect_configuration_warnings(fl=fl, bind_host="127.0.0.1", bind_port=8000)
    gw = next(x for x in w if x["code"] == "gateway_forward_blocked_names")
    assert "authorization, cookie" in gw["message"]


def test_collect_warnings_combined_0_11_gateway_forward_and_trust_proxy_body() -> None:
    fl = FluxLit(
        settings=FluxlitSettings(
            trust_proxy=True,
            gateway_max_proxy_request_body_bytes=0,
            gateway_forward_client_headers_to_streamlit=["Authorization", "x-request-id"],
        )
    )
    w = collect_configuration_warnings(fl=fl, bind_host="127.0.0.1", bind_port=8000)
    codes = {x["code"] for x in w}
    assert "gateway_forward_blocked_names" in codes
    assert "gateway_max_body_unlimited_trust_proxy" in codes


def test_collect_warnings_no_forward_blocked_when_allowlist_only_safe_names() -> None:
    fl = FluxLit(
        settings=FluxlitSettings(
            gateway_forward_client_headers_to_streamlit=["traceparent", "x-request-id"]
        )
    )
    w = collect_configuration_warnings(fl=fl, bind_host="127.0.0.1", bind_port=8000)
    assert all(x["code"] != "gateway_forward_blocked_names" for x in w)


def test_collect_warnings_no_unlimited_body_warn_when_limit_set_with_trust_proxy() -> None:
    fl = FluxLit(
        settings=FluxlitSettings(
            trust_proxy=True,
            gateway_max_proxy_request_body_bytes=1048576,
        )
    )
    w = collect_configuration_warnings(fl=fl, bind_host="127.0.0.1", bind_port=8000)
    assert all(x["code"] != "gateway_max_body_unlimited_trust_proxy" for x in w)
