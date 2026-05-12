from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest
from typer.testing import CliRunner

import fluxlit.cli as cli_module
from fluxlit.cli import app
from fluxlit.runtime import find_free_port


def test_doctor_prints_checks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    port = find_free_port()
    module_path = tmp_path / "demo_cli_app.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n\n"
        f"app = FluxLit(title='CLI App', settings=FluxlitSettings(gateway_port={port}))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "demo_cli_app:app"])
    assert res.exit_code == 0
    assert "FluxLit doctor" in res.stdout
    assert "PASS" in res.stdout
    assert "import_target:" in res.stdout
    assert "demo_cli_app:app" in res.stdout


def test_doctor_check_pages_runs_pages_validate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    port = find_free_port()
    module_path = tmp_path / "doc_pages_app.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n\n"
        f"app = FluxLit(title='D', settings=FluxlitSettings(gateway_port={port}))\n\n"
        "@app.page('/')\n"
        "def h(st, client):\n"
        "    del st, client\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "doc_pages_app:app", "--check-pages"])
    assert res.exit_code == 0
    assert "pages_validate" in res.stdout


def test_doctor_check_pages_warns_experimental_yield(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FLUXLIT_EXPERIMENTAL_YIELD_PAGES", "1")
    port = find_free_port()
    module_path = tmp_path / "doc_yield_app.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n\n"
        f"app = FluxLit(title='Y', settings=FluxlitSettings(gateway_port={port}))\n\n"
        "@app.page('/')\n"
        "def h(st, client):\n"
        "    del st, client\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "doc_yield_app:app", "--check-pages"])
    assert res.exit_code == 0
    assert "experimental_yield_pages" in res.stdout


def test_doctor_check_pages_fails_when_validate_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fluxlit.pages.validate as vmod

    port = find_free_port()
    module_path = tmp_path / "doc_bad_pages_app.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n\n"
        f"app = FluxLit(title='B', settings=FluxlitSettings(gateway_port={port}))\n\n"
        "@app.page('/')\n"
        "def h(st, client):\n"
        "    del st, client\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(
        vmod,
        "validate_fluxlit_pages",
        lambda *_a, **_k: ["manifest JSON: forced failure for doctor test"],
    )
    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "doc_bad_pages_app:app", "--check-pages"])
    assert res.exit_code == 1
    assert "pages_validate" in res.stdout
    assert "FAIL" in res.stdout


def test_doctor_verbose_prints_effective_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    port = find_free_port()
    module_path = tmp_path / "demo_cli_verbose_app.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n\n"
        f"app = FluxLit(title='V', settings=FluxlitSettings(gateway_port={port}))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "demo_cli_verbose_app:app", "--verbose"])
    assert res.exit_code == 0
    assert "Verbose (effective configuration" in res.stdout
    assert "resolved_target: demo_cli_verbose_app:app" in res.stdout
    assert "internal_api_base (derived for Streamlit)" in res.stdout


def test_doctor_json_verbose_includes_verbose_object(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    port = find_free_port()
    module_path = tmp_path / "demo_cli_json_verbose_app.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n\n"
        f"app = FluxLit(title='JV', settings=FluxlitSettings(gateway_port={port}))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "demo_cli_json_verbose_app:app", "--json", "--verbose"])
    assert res.exit_code == 0
    payload = json.loads(res.stdout)
    assert "verbose" in payload
    assert payload["verbose"]["resolved_target"] == "demo_cli_json_verbose_app:app"
    assert "effective" in payload["verbose"]


def test_doctor_json_without_verbose_omits_verbose_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    port = find_free_port()
    module_path = tmp_path / "demo_cli_json_no_verbose.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n\n"
        f"app = FluxLit(settings=FluxlitSettings(gateway_port={port}))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "demo_cli_json_no_verbose:app", "--json"])
    assert res.exit_code == 0
    assert "verbose" not in json.loads(res.stdout)


def test_doctor_collect_verbose_import_failed_detail() -> None:
    from fluxlit.config import load_project_config

    rows, detail = cli_module._doctor_collect(  # noqa: SLF001
        "nonexistent_module_xyz_fluxlit:app",
        load_project_config(),
        verbose=True,
    )
    assert detail == {
        "resolved_target": "nonexistent_module_xyz_fluxlit:app",
        "import_failed": True,
    }
    assert any(name == "import_target" and status == "FAIL" for name, status, _ in rows)


def test_doctor_checks_passes_verbose_to_collect() -> None:
    rows = cli_module._doctor_checks("tests.e2e.minimal_app:app", verbose=True)  # noqa: SLF001
    assert any(name == "import_target" and status == "PASS" for name, status, _ in rows)


def test_doctor_json_verbose_import_failed_includes_verbose_stub(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = tmp_path / "broken_verbose_json_app.py"
    module_path.write_text("# not a FluxLit instance\napp = 123\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "broken_verbose_json_app:app", "--json", "--verbose"])
    assert res.exit_code == 1
    payload = json.loads(res.stdout)
    assert payload["verbose"]["import_failed"] is True


def test_doctor_collect_gateway_bind_ipv6_wildcard_maps_to_loopback_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = tmp_path / "doctor_v6_wild_bind_app.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n"
        "app = FluxLit(settings=FluxlitSettings(gateway_host='::', gateway_port=59498))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    seen: list[tuple[object, ...]] = []

    def capture_getaddrinfo(host: object, port: object, *args: object, **kwargs: object) -> list:
        seen.append((host, port))
        return [
            (
                cli_module.socket.AF_INET6,
                cli_module.socket.SOCK_STREAM,
                0,
                "",
                ("::1", int(port), 0, 0),
            )
        ]

    monkeypatch.setattr(cli_module.socket, "getaddrinfo", capture_getaddrinfo)

    class FakeSocket:
        def __init__(self, family: int, socktype: int, proto: int) -> None:
            self.family = family

        def __enter__(self) -> FakeSocket:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def setsockopt(self, *args: object) -> None:
            return None

        def bind(self, addr: tuple[object, ...]) -> None:
            return None

    monkeypatch.setattr(cli_module.socket, "socket", FakeSocket)
    rows = cli_module._doctor_checks("doctor_v6_wild_bind_app:app")  # noqa: SLF001
    assert any(name == "gateway_bind" and status == "PASS" for name, status, _ in rows)
    assert seen and seen[0][0] == "::1"


def test_doctor_collect_bind_host_zero_resolves_to_loopback_for_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = tmp_path / "doctor_zero_bind_app.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n"
        "app = FluxLit(settings=FluxlitSettings(gateway_host='0.0.0.0', gateway_port=59497))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    seen: list[tuple[object, ...]] = []

    def capture_getaddrinfo(host: object, port: object, *args: object, **kwargs: object) -> list:
        seen.append((host, port))
        return [
            (
                cli_module.socket.AF_INET,
                cli_module.socket.SOCK_STREAM,
                0,
                "",
                (host, int(port)),
            )
        ]

    monkeypatch.setattr(cli_module.socket, "getaddrinfo", capture_getaddrinfo)

    class FakeSocket:
        def __init__(self, family: int, socktype: int, proto: int) -> None:
            pass

        def __enter__(self) -> FakeSocket:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def setsockopt(self, *args: object) -> None:
            return None

        def bind(self, addr: tuple[object, ...]) -> None:
            return None

    monkeypatch.setattr(cli_module.socket, "socket", FakeSocket)
    rows = cli_module._doctor_checks("doctor_zero_bind_app:app")  # noqa: SLF001
    assert any(name == "gateway_bind" and status == "PASS" for name, status, _ in rows)
    assert seen and seen[0][0] == "127.0.0.1"


def test_doctor_json_outputs_structured_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    port = find_free_port()
    module_path = tmp_path / "demo_cli_json_app.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n\n"
        f"app = FluxLit(title='CLI JSON App', settings=FluxlitSettings(gateway_port={port}))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "demo_cli_json_app:app", "--json"])
    assert res.exit_code == 0
    payload = json.loads(res.stdout)
    assert payload["status"] in {"pass", "warn"}
    assert payload["target"] == "demo_cli_json_app:app"
    assert {
        "name": "import_target",
        "status": "PASS",
        "detail": "demo_cli_json_app:app",
    } in payload["checks"]


def test_doctor_json_failure_reports_fail_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = tmp_path / "broken_json_app.py"
    module_path.write_text("# not a FluxLit instance\napp = 123\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))

    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "broken_json_app:app", "--json"])
    assert res.exit_code == 1
    payload = json.loads(res.stdout)
    assert payload["status"] == "fail"
    assert any(c["name"] == "import_target" and c["status"] == "FAIL" for c in payload["checks"])


def test_doctor_json_warnings_only_exits_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = tmp_path / "broken_json_warn_app.py"
    module_path.write_text("# not a FluxLit instance\napp = 123\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))

    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "broken_json_warn_app:app", "--json", "--warnings-only"])
    assert res.exit_code == 0
    payload = json.loads(res.stdout)
    assert payload["status"] == "warn"
    assert payload["warnings_only"] is True


def test_doctor_json_warning_status_and_check_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    port = find_free_port()
    module_path = tmp_path / "doc_json_warn_only.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n\n"
        "app = FluxLit(settings=FluxlitSettings("
        f"trust_proxy=True, forwarded_allow_ips='*', gateway_port={port}))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "doc_json_warn_only:app", "--json"])
    assert res.exit_code == 0
    assert "FluxLit doctor" not in res.stdout
    payload = json.loads(res.stdout)
    assert payload["status"] == "warn"
    assert payload["warnings_only"] is False
    assert payload["target"] == "doc_json_warn_only:app"
    assert all(set(check) == {"name", "status", "detail"} for check in payload["checks"])
    assert any(
        check["name"] == "forwarded_allow_ips" and check["status"] == "WARN"
        for check in payload["checks"]
    )


def test_doctor_json_missing_upstream_file_reports_structured_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    port = find_free_port()
    module_path = tmp_path / "doc_json_missing_upstream.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n\n"
        f"app = FluxLit(settings=FluxlitSettings(gateway_port={port}))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv("FLUXLIT_STREAMLIT_UPSTREAM_FILE", str(tmp_path / "missing.txt"))

    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "doc_json_missing_upstream:app", "--json"])
    assert res.exit_code == 1
    payload = json.loads(res.stdout)
    assert payload["status"] == "fail"
    assert any(
        check["name"] == "streamlit_upstream_state"
        and check["status"] == "FAIL"
        and "state file missing" in check["detail"]
        for check in payload["checks"]
    )


def test_doctor_warns_when_internal_api_path_mismatches_mount(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    port = find_free_port()
    module_path = tmp_path / "doc_mount_app.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n\n"
        "app = FluxLit(title='M', settings=FluxlitSettings("
        f"api_mount_path='/api/v1', gateway_port={port}))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FLUXLIT_INTERNAL_API_BASE", f"http://127.0.0.1:{port}/api")

    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "doc_mount_app:app"])
    assert res.exit_code == 0
    assert "WARN" in res.stdout
    assert "api_mount_path" in res.stdout


def test_doctor_passes_proxy_headers_when_subpath_and_trust_proxy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    port = find_free_port()
    module_path = tmp_path / "doc_subpath_trust_ok.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n\n"
        "app = FluxLit(title='ST', settings=FluxlitSettings("
        "root_path='/content/1', trust_proxy=True, public_base_url='https://example.com', "
        f"gateway_port={port}))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "doc_subpath_trust_ok:app"])
    assert res.exit_code == 0
    assert "proxy_headers" in res.stdout
    assert "PASS" in res.stdout
    assert "trust_proxy enabled" in res.stdout


def test_doctor_warns_when_trust_proxy_has_broad_forwarded_allow_ips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    port = find_free_port()
    module_path = tmp_path / "doc_proxy_broad.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n\n"
        "app = FluxLit(settings=FluxlitSettings("
        f"trust_proxy=True, forwarded_allow_ips='*', gateway_port={port}))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "doc_proxy_broad:app"])
    assert res.exit_code == 0
    assert "forwarded_allow_ips" in res.stdout
    assert "WARN" in res.stdout


def test_doctor_warns_when_public_base_url_path_mismatches_root_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    port = find_free_port()
    module_path = tmp_path / "doc_public_base_mismatch.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n\n"
        "app = FluxLit(settings=FluxlitSettings("
        "root_path='/apps/demo', public_base_url='https://example.com/wrong', "
        f"gateway_port={port}))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "doc_public_base_mismatch:app"])
    assert res.exit_code == 0
    assert "public_base_url" in res.stdout
    assert "does not match public mount" in res.stdout


def test_doctor_fails_missing_streamlit_upstream_state_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    port = find_free_port()
    module_path = tmp_path / "doc_missing_upstream_file.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n\n"
        f"app = FluxLit(settings=FluxlitSettings(gateway_port={port}))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv("FLUXLIT_STREAMLIT_UPSTREAM_FILE", str(tmp_path / "missing.txt"))
    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "doc_missing_upstream_file:app"])
    assert res.exit_code == 1
    assert "streamlit_upstream_state" in res.stdout
    assert "state file missing" in res.stdout


def test_doctor_fails_fluxlit_auth_extra_when_pyjwt_unimportable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port = find_free_port()
    module_path = tmp_path / "doc_jwt_blocked.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n\n"
        f"app = FluxLit(title='B', settings=FluxlitSettings(gateway_port={port}))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv("FLUXLIT_JWT_ISSUER", "https://issuer.blocked")
    prior = sys.modules.pop("jwt", None)
    sys.modules["jwt"] = None
    try:
        runner = CliRunner()
        res = runner.invoke(app, ["doctor", "doc_jwt_blocked:app"])
        assert res.exit_code == 1
        assert "fluxlit_auth_extra" in res.stdout
        assert "FAIL" in res.stdout
    finally:
        sys.modules.pop("jwt", None)
        if prior is not None:
            sys.modules["jwt"] = prior


def test_doctor_reports_auth_extra_when_jwt_env_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    port = find_free_port()
    module_path = tmp_path / "doc_jwt_env.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n\n"
        f"app = FluxLit(title='J', settings=FluxlitSettings(gateway_port={port}))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv("FLUXLIT_JWT_ISSUER", "https://issuer.example")
    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "doc_jwt_env:app"])
    assert res.exit_code == 0
    assert "fluxlit_auth_extra" in res.stdout
    assert "PyJWT" in res.stdout


def test_doctor_warns_when_subpath_without_trust_proxy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    port = find_free_port()
    module_path = tmp_path / "doc_subpath_proxy.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n\n"
        "app = FluxLit(title='S', settings=FluxlitSettings("
        "root_path='/content/1', trust_proxy=False, public_base_url='https://example.com', "
        f"gateway_port={port}))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "doc_subpath_proxy:app"])
    assert res.exit_code == 0
    assert "proxy_headers" in res.stdout
    assert "FLUXLIT_TRUST_PROXY" in res.stdout


def test_doctor_passes_when_internal_api_path_matches_mount(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    port = find_free_port()
    module_path = tmp_path / "doc_mount_ok.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n\n"
        "app = FluxLit(title='M', settings=FluxlitSettings("
        f"api_mount_path='/api/v1', gateway_port={port}))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FLUXLIT_INTERNAL_API_BASE", f"http://127.0.0.1:{port}/api/v1")

    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "doc_mount_ok:app"])
    assert res.exit_code == 0
    assert "FLUXLIT_INTERNAL_API_BASE" in res.stdout
    assert "matches api_mount_path" in res.stdout


def test_doctor_exit_one_on_failure_without_warnings_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = tmp_path / "broken_app2.py"
    module_path.write_text("# not a FluxLit instance\napp = 123\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))

    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "broken_app2:app"])
    assert res.exit_code == 1
    assert "FAIL" in res.stdout


def test_doctor_warnings_only_exit_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module_path = tmp_path / "broken_app.py"
    module_path.write_text("# not a FluxLit instance\napp = 123\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))

    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "broken_app:app", "--warnings-only"])
    assert res.exit_code == 0
    assert "FAIL" in res.stdout


def test_dev_invalid_reload_scope_exits_two(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "reload_app.py").write_text(
        "from fluxlit import FluxLit\napp = FluxLit(title='R')\n", encoding="utf-8"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    res = runner.invoke(
        app,
        ["dev", "reload_app:app", "--reload", "--reload-scope", "bogus"],
        catch_exceptions=False,
    )
    assert res.exit_code == 2
    assert "reload-scope" in res.stderr.lower()


def test_dev_passes_reload_scope_full_to_run_unified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "reload_full_app.py").write_text(
        "from fluxlit import FluxLit\napp = FluxLit(title='RF')\n", encoding="utf-8"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)
    called: dict[str, object] = {}

    def stub(target: str, **kwargs: object) -> None:
        called["target"] = target
        called.update(kwargs)

    monkeypatch.setattr("fluxlit.cli.run_unified", stub)
    runner = CliRunner()
    res = runner.invoke(
        app,
        ["dev", "reload_full_app:app", "--reload", "--reload-scope", "full"],
        catch_exceptions=False,
    )
    assert res.exit_code == 0
    assert called.get("reload_scope") == "full"


def test_dev_debug_sets_fluxlit_debug_environment_variable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "dbg_cli_app.py").write_text(
        "from fluxlit import FluxLit\napp = FluxLit(title='DBG')\n", encoding="utf-8"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)
    prev_debug = os.environ.pop("FLUXLIT_DEBUG", None)
    try:

        def stub(*_a: object, **_k: object) -> None:
            return None

        monkeypatch.setattr("fluxlit.cli.run_unified", stub)
        runner = CliRunner()
        res = runner.invoke(app, ["dev", "dbg_cli_app:app", "--debug"], catch_exceptions=False)
        assert res.exit_code == 0
        assert os.environ.get("FLUXLIT_DEBUG") == "1"
    finally:
        if prev_debug is None:
            os.environ.pop("FLUXLIT_DEBUG", None)
        else:
            os.environ["FLUXLIT_DEBUG"] = prev_debug


def test_dev_resolves_target_fluxlit_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "fluxlit.toml").write_text('target = "toml_app:app"\n', encoding="utf-8")
    (tmp_path / "toml_app.py").write_text(
        "from fluxlit import FluxLit\napp = FluxLit(title='T')\n", encoding="utf-8"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)

    called: dict[str, object] = {}

    def fake_run_unified(target: str, **kwargs: object) -> None:
        called["target"] = target
        called.update(kwargs)

    monkeypatch.setattr("fluxlit.cli.run_unified", fake_run_unified)

    runner = CliRunner()
    res = runner.invoke(app, ["dev"], catch_exceptions=False)
    assert res.exit_code == 0
    assert called["target"] == "toml_app:app"


def test_build_refuses_overwrite_without_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    (out / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")

    runner = CliRunner()
    res = runner.invoke(app, ["build", "-o", str(out), "app:app"])
    assert res.exit_code == 1
    assert "--force" in res.stderr or "force" in res.stderr.lower()


def test_build_writes_docker_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    res = runner.invoke(app, ["build", "--force", "-o", str(tmp_path / "out"), "app:app"])
    assert res.exit_code == 0
    df = tmp_path / "out" / "Dockerfile"
    assert df.is_file()
    body = df.read_text(encoding="utf-8")
    assert "fluxlit" in body
    assert 'CMD ["fluxlit", "run", "app:app"]' in body
    assert "USER appuser" in body
    assert "FROM python@sha256:" in body
    assert (tmp_path / "out" / ".dockerignore").is_file()


def test_run_invokes_unified_without_reload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "run_app.py").write_text(
        "from fluxlit import FluxLit\napp = FluxLit(title='Run')\n", encoding="utf-8"
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    called: dict[str, object] = {}

    def stub(target: str, **kwargs: object) -> None:
        called["target"] = target
        called.update(kwargs)

    monkeypatch.setattr("fluxlit.cli.run_unified", stub)
    runner = CliRunner()
    res = runner.invoke(app, ["run", "run_app:app"], catch_exceptions=False)
    assert res.exit_code == 0
    assert called["target"] == "run_app:app"
    assert called["reload"] is False


def test_new_scaffold_writes_app_py(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    res = runner.invoke(app, ["new", "scaffold_demo"], catch_exceptions=False)
    assert res.exit_code == 0
    root = tmp_path / "scaffold_demo"
    app_py = root / "app.py"
    assert app_py.is_file()
    assert "FluxLit" in app_py.read_text(encoding="utf-8")
    assert "Depends" in app_py.read_text(encoding="utf-8")
    toml = root / "fluxlit.toml"
    assert toml.is_file()
    assert 'target = "app:app"' in toml.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("profile", "expected"),
    [
        ("minimal", "FluxLit Demo"),
        ("auth-ready", "Auth-ready Dashboard"),
        ("deploy", "Deployment Dashboard"),
    ],
)
def test_new_scaffold_profiles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    profile: str,
    expected: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    res = runner.invoke(
        app,
        ["new", f"scaffold_{profile}", "--profile", profile],
        catch_exceptions=False,
    )
    assert res.exit_code == 0
    assert profile in res.stdout
    assert expected in (tmp_path / f"scaffold_{profile}" / "app.py").read_text(encoding="utf-8")


def test_new_exits_when_destination_exists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "exists").mkdir()
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    res = runner.invoke(app, ["new", "exists"])
    assert res.exit_code == 1


def test_dev_defaults_come_from_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Validates that `fluxlit dev` uses the app settings for host/port/log_level when omitted.
    """
    module_path = tmp_path / "demo_defaults_app.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n\n"
        "settings = FluxlitSettings(\n"
        "    gateway_host='0.0.0.0',\n"
        "    gateway_port=7777,\n"
        "    log_level='warning',\n"
        ")\n"
        "app = FluxLit(title='Defaults', settings=settings)\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    called = {}

    def fake_run_unified(target: str, **kwargs: object) -> None:
        called["target"] = target
        called.update(kwargs)

    monkeypatch.setattr("fluxlit.cli.run_unified", fake_run_unified)

    runner = CliRunner()
    res = runner.invoke(app, ["dev", "demo_defaults_app:app"])
    assert res.exit_code == 0

    assert called["target"] == "demo_defaults_app:app"
    assert called["host"] == "0.0.0.0"
    assert called["port"] == 7777
    assert called["log_level"] == "warning"


def test_shutdown_no_pidfile_exits_two(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    res = runner.invoke(app, ["shutdown"], catch_exceptions=False)
    assert res.exit_code == 2
    assert "No pid file" in res.stdout


def test_shutdown_exits_zero_on_stale_pid(tmp_path: Path) -> None:
    pid_path = tmp_path / ".fluxlit-dev.pid"
    pid_path.write_text("999999999\n", encoding="ascii")
    runner = CliRunner()
    res = runner.invoke(app, ["shutdown", "--pidfile", str(pid_path)], catch_exceptions=False)
    assert res.exit_code == 0
    assert not pid_path.exists()


def test_shutdown_sends_sigterm_to_recorded_pid(tmp_path: Path) -> None:
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    pid_path = tmp_path / "sub.pid"
    pid_path.write_text(f"{proc.pid}\n", encoding="ascii")
    try:
        runner = CliRunner()
        res = runner.invoke(
            app,
            ["shutdown", "--pidfile", str(pid_path), "--wait", "5"],
            catch_exceptions=False,
        )
        assert res.exit_code == 0
        proc.wait(timeout=15)
        assert proc.returncode is not None
    finally:
        with contextlib.suppress(Exception):
            proc.kill()
            proc.wait(timeout=3)


def test_tcp_url_reachable_validation_success_and_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert cli_module._tcp_url_reachable("not-a-url")[0] is False  # noqa: SLF001

    class Conn:
        def __enter__(self) -> Conn:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    seen: list[tuple[str, int]] = []

    def connect(addr: tuple[str, int], timeout: float) -> Conn:
        seen.append(addr)
        return Conn()

    monkeypatch.setattr(cli_module.socket, "create_connection", connect)
    ok, msg = cli_module._tcp_url_reachable("https://example.com/path")  # noqa: SLF001
    assert ok is True
    assert seen == [("example.com", 443)]
    assert "reachable" in msg

    def fail(addr: tuple[str, int], timeout: float) -> Conn:
        raise OSError("closed")

    monkeypatch.setattr(cli_module.socket, "create_connection", fail)
    ok, msg = cli_module._tcp_url_reachable("http://example.com:8080")  # noqa: SLF001
    assert ok is False
    assert "unreachable" in msg


def test_doctor_checks_dependency_import_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = __import__

    def fake_import(name: str, *args: object, **kwargs: object):
        if name == "httpx":
            raise ImportError("blocked httpx")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    rows = cli_module._doctor_checks("definitely_missing_cli_cov:app")  # noqa: SLF001
    assert ("dependencies", "FAIL", "blocked httpx") in rows


def test_doctor_checks_streamlit_version_warn_and_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = tmp_path / "doctor_version_app.py"
    module_path.write_text(
        "from fluxlit import FluxLit\napp = FluxLit()\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setitem(sys.modules, "streamlit", types.SimpleNamespace(__version__="1.20.0"))
    rows = cli_module._doctor_checks("doctor_version_app:app")  # noqa: SLF001
    assert any(name == "streamlit_version" and status == "WARN" for name, status, _ in rows)

    class BadStreamlit:
        @property
        def __version__(self) -> str:
            raise RuntimeError("no version")

    monkeypatch.setitem(sys.modules, "streamlit", BadStreamlit())
    rows = cli_module._doctor_checks("doctor_version_app:app")  # noqa: SLF001
    assert any(
        name == "streamlit_version" and status == "WARN" and "no version" in detail
        for name, status, detail in rows
    )


def test_doctor_checks_gateway_bind_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = tmp_path / "doctor_bind_app.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n"
        "app = FluxLit(settings=FluxlitSettings(gateway_port=59401))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    class FailingSocket:
        def __enter__(self) -> FailingSocket:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def setsockopt(self, *args: object) -> None:
            return None

        def bind(self, addr: tuple[str, int]) -> None:
            raise OSError("address already in use")

    monkeypatch.setattr(cli_module.socket, "socket", lambda *args, **kwargs: FailingSocket())
    rows = cli_module._doctor_checks("doctor_bind_app:app")  # noqa: SLF001
    assert any(name == "gateway_bind" and status == "FAIL" for name, status, _ in rows)


def test_doctor_checks_gateway_bind_uses_ipv6_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = tmp_path / "doctor_ipv6_bind_app.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n"
        "app = FluxLit(settings=FluxlitSettings(gateway_host='::1', gateway_port=59401))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(
        cli_module.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (
                cli_module.socket.AF_INET6,
                cli_module.socket.SOCK_STREAM,
                0,
                "",
                ("::1", 59401, 0, 0),
            )
        ],
    )
    captured: dict[str, object] = {}

    class FakeSocket:
        def __init__(self, family: int, socktype: int, proto: int) -> None:
            captured["family"] = family
            captured["socktype"] = socktype
            captured["proto"] = proto

        def __enter__(self) -> FakeSocket:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def setsockopt(self, *args: object) -> None:
            return None

        def bind(self, addr: tuple[str, int, int, int]) -> None:
            captured["addr"] = addr

    monkeypatch.setattr(cli_module.socket, "socket", FakeSocket)
    rows = cli_module._doctor_checks("doctor_ipv6_bind_app:app")  # noqa: SLF001
    assert any(name == "gateway_bind" and status == "PASS" for name, status, _ in rows)
    assert captured["family"] == cli_module.socket.AF_INET6
    assert captured["addr"] == ("::1", 59401, 0, 0)


def test_doctor_checks_gateway_bind_fails_when_host_does_not_resolve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = tmp_path / "doctor_unresolved_bind_app.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n"
        "app = FluxLit(settings=FluxlitSettings(\n"
        "    gateway_host='missing.local', gateway_port=59401\n"
        "))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(cli_module.socket, "getaddrinfo", lambda *args, **kwargs: [])
    rows = cli_module._doctor_checks("doctor_unresolved_bind_app:app")  # noqa: SLF001
    assert any(
        name == "gateway_bind" and status == "FAIL" and "could not resolve" in detail
        for name, status, detail in rows
    )


def test_doctor_checks_warns_on_ambiguous_import_candidates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "app.py").write_text(
        "from fluxlit import FluxLit\napp = FluxLit()\n", encoding="utf-8"
    )
    app_pkg = second / "app"
    app_pkg.mkdir()
    (app_pkg / "__init__.py").write_text(
        "from fluxlit import FluxLit\napp = FluxLit()\n", encoding="utf-8"
    )
    monkeypatch.syspath_prepend(str(second))
    monkeypatch.syspath_prepend(str(first))

    rows = cli_module._doctor_checks("app:app")  # noqa: SLF001
    assert any(name == "sys_path_head" and status == "PASS" for name, status, _ in rows)
    assert any(
        name == "import_shadowing" and status == "WARN" and "multiple import candidates" in detail
        for name, status, detail in rows
    )


def test_doctor_checks_internal_api_invalid_and_import_failed_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FLUXLIT_INTERNAL_API_BASE", "not-absolute")
    rows = cli_module._doctor_checks("definitely_missing_cli_cov:app")  # noqa: SLF001
    assert (
        "FLUXLIT_INTERNAL_API_BASE",
        "FAIL",
        "not a valid absolute URL",
    ) in rows

    monkeypatch.setenv("FLUXLIT_INTERNAL_API_BASE", "http://127.0.0.1:8000/api")
    rows = cli_module._doctor_checks("definitely_missing_cli_cov:app")  # noqa: SLF001
    assert any(
        name == "FLUXLIT_INTERNAL_API_BASE" and status == "PASS" and "import failed" in detail
        for name, status, detail in rows
    )


def test_doctor_checks_public_url_forwarded_and_security_warnings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = tmp_path / "doctor_misc_app.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n"
        "app = FluxLit(settings=FluxlitSettings(\n"
        "    public_base_url='not-a-url',\n"
        "    trust_proxy=True,\n"
        "    forwarded_allow_ips='127.0.0.1',\n"
        "    cors_allow_origins=['https://app.example'],\n"
        "    enable_security_headers=False,\n"
        "    gateway_port=59402,\n"
        "))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    rows = cli_module._doctor_checks("doctor_misc_app:app")  # noqa: SLF001
    assert ("forwarded_allow_ips", "PASS", "127.0.0.1") in rows
    assert ("public_base_url", "FAIL", "not a valid absolute URL") in rows
    assert any(name == "security_headers" and status == "WARN" for name, status, _ in rows)


def test_doctor_checks_public_base_url_precedence_and_config_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = tmp_path / "doctor_public_base_app.py"
    module_path.write_text("from fluxlit import FluxLit\napp = FluxLit()\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://legacy.example")
    monkeypatch.setenv("FLUXLIT_PUBLIC_BASE_URL", "https://fluxlit.example")
    rows = cli_module._doctor_checks("doctor_public_base_app:app")  # noqa: SLF001
    assert any(name == "import_module_file" and status == "PASS" for name, status, _ in rows)
    assert ("config.api_mount_path", "PASS", "/api") in rows
    assert any(
        name == "public_base_url_precedence" and status == "WARN" and "FluxLit uses" in detail
        for name, status, detail in rows
    )


def test_doctor_checks_public_base_url_strict_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = tmp_path / "doctor_public_base_strict_app.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n"
        "app = FluxLit(settings=FluxlitSettings(strict_public_base_url=True))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://legacy.example")
    monkeypatch.setenv("FLUXLIT_PUBLIC_BASE_URL", "https://fluxlit.example")
    rows = cli_module._doctor_checks("doctor_public_base_strict_app:app")  # noqa: SLF001
    assert any(
        name == "public_base_url_precedence" and status == "FAIL" for name, status, _ in rows
    )


def test_doctor_checks_metrics_extra_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = tmp_path / "doctor_metrics_app.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n"
        "app = FluxLit(settings=FluxlitSettings(enable_gateway_prometheus_metrics=True))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(cli_module, "find_spec", lambda name: None)
    rows = cli_module._doctor_checks("doctor_metrics_app:app")  # noqa: SLF001
    assert any(
        name == "fluxlit_metrics_extra" and status == "FAIL" and "fluxlit[metrics]" in detail
        for name, status, detail in rows
    )


def test_doctor_checks_metrics_extra_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = tmp_path / "doctor_metrics_present_app.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n"
        "app = FluxLit(settings=FluxlitSettings(enable_gateway_prometheus_metrics=True))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(cli_module, "find_spec", lambda name: object())
    rows = cli_module._doctor_checks("doctor_metrics_present_app:app")  # noqa: SLF001
    assert ("fluxlit_metrics_extra", "PASS", "prometheus-client importable") in rows


def test_doctor_checks_public_base_url_single_source_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = tmp_path / "doctor_public_base_single_app.py"
    module_path.write_text("from fluxlit import FluxLit\napp = FluxLit()\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))

    monkeypatch.setenv("FLUXLIT_PUBLIC_BASE_URL", "https://fluxlit.example")
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    rows = cli_module._doctor_checks("doctor_public_base_single_app:app")  # noqa: SLF001
    assert ("public_base_url_precedence", "PASS", "using FLUXLIT_PUBLIC_BASE_URL") in rows

    monkeypatch.delenv("FLUXLIT_PUBLIC_BASE_URL", raising=False)
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://legacy.example")
    rows = cli_module._doctor_checks("doctor_public_base_single_app:app")  # noqa: SLF001
    assert ("public_base_url_precedence", "PASS", "using PUBLIC_BASE_URL fallback") in rows


def test_doctor_checks_oauth_public_base_url_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = tmp_path / "doctor_oauth_base_app.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n"
        "app = FluxLit(settings=FluxlitSettings(root_path='/content/2', gateway_port=59412))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    rows = cli_module._doctor_checks("doctor_oauth_base_app:app")  # noqa: SLF001
    assert any(name == "oauth_public_base_url" and status == "WARN" for name, status, _ in rows)


def test_doctor_checks_upstream_state_file_and_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = tmp_path / "doctor_upstream_app.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n"
        "app = FluxLit(settings=FluxlitSettings(gateway_port=59403))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    state_file = tmp_path / "upstream.txt"
    state_file.write_text("", encoding="utf-8")
    monkeypatch.setenv("FLUXLIT_STREAMLIT_UPSTREAM_FILE", str(state_file))
    rows = cli_module._doctor_checks("doctor_upstream_app:app")  # noqa: SLF001
    assert any(
        name == "streamlit_upstream_state" and status == "WARN" and "empty" in detail
        for name, status, detail in rows
    )

    state_file.write_text("http://127.0.0.1:9\n", encoding="utf-8")
    monkeypatch.setattr(cli_module, "_tcp_url_reachable", lambda url: (True, f"{url} ok"))
    rows = cli_module._doctor_checks("doctor_upstream_app:app")  # noqa: SLF001
    assert ("streamlit_upstream_state", "PASS", "http://127.0.0.1:9 ok") in rows

    monkeypatch.delenv("FLUXLIT_STREAMLIT_UPSTREAM_FILE", raising=False)
    monkeypatch.setenv("FLUXLIT_STREAMLIT_UPSTREAM", "http://127.0.0.1:9")
    rows = cli_module._doctor_checks("doctor_upstream_app:app")  # noqa: SLF001
    assert ("streamlit_upstream", "PASS", "http://127.0.0.1:9 ok") in rows


def test_doctor_warns_gateway_upstream_read_timeout_when_low(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port = find_free_port()
    module_path = tmp_path / "doc_low_gateway_read.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n"
        f"app = FluxLit(settings=FluxlitSettings(gateway_port={port}, "
        "gateway_upstream_read_timeout_s=1.0))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    rows = cli_module._doctor_checks("doc_low_gateway_read:app")  # noqa: SLF001
    assert any(name == "gateway_upstream_timeouts" and status == "WARN" for name, status, _ in rows)


def test_doctor_warns_async_depends_when_enabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port = find_free_port()
    module_path = tmp_path / "doc_async_dep.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n"
        f"app = FluxLit(settings=FluxlitSettings(gateway_port={port}, async_page_depends=True))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    rows = cli_module._doctor_checks("doc_async_dep:app")  # noqa: SLF001
    assert any(name == "async_depends_streamlit" and status == "WARN" for name, status, _ in rows)


def test_doctor_warns_gateway_forward_headers_when_configured(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port = find_free_port()
    module_path = tmp_path / "doc_fwd_hdr.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n"
        f"app = FluxLit(settings=FluxlitSettings(gateway_port={port}, "
        "gateway_forward_client_headers_to_streamlit=['traceparent']))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    rows = cli_module._doctor_checks("doc_fwd_hdr:app")  # noqa: SLF001
    assert any(
        name == "gateway_forward_client_headers" and status == "WARN" for name, status, _ in rows
    )


def test_doctor_warns_gateway_forward_rejected_sensitive_names(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port = find_free_port()
    module_path = tmp_path / "doc_fwd_reject.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n"
        f"app = FluxLit(settings=FluxlitSettings(gateway_port={port}, "
        "gateway_forward_client_headers_to_streamlit=['Authorization', 'traceparent']))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    rows = cli_module._doctor_checks("doc_fwd_reject:app")  # noqa: SLF001
    row = next(
        (name, status, detail)
        for name, status, detail in rows
        if name == "gateway_forward_rejected_names" and status == "WARN"
    )
    assert "authorization" in row[2].lower()
    assert "never forwarded" in row[2].lower()


def test_doctor_gateway_forward_rejected_lists_multiple_names(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port = find_free_port()
    module_path = tmp_path / "doc_fwd_reject_multi.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n"
        f"app = FluxLit(settings=FluxlitSettings(gateway_port={port}, "
        "gateway_forward_client_headers_to_streamlit=['Cookie', 'Authorization', 'x-foo']))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    rows = cli_module._doctor_checks("doc_fwd_reject_multi:app")  # noqa: SLF001
    detail = next(d for n, _, d in rows if n == "gateway_forward_rejected_names")
    assert "'authorization'" in detail or "authorization" in detail
    assert "cookie" in detail.lower()


def test_doctor_default_010_operational_rows_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default app: readiness hint, WebSocket note, timeouts OK, no async deps, no header bridge."""
    port = find_free_port()
    module_path = tmp_path / "doc_default_010.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "from fluxlit.config import FluxlitSettings\n"
        f"app = FluxLit(settings=FluxlitSettings(gateway_port={port}))\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    rows = cli_module._doctor_checks("doc_default_010:app")  # noqa: SLF001
    by_name = {name: (status, detail) for name, status, detail in rows}
    assert by_name["readiness_route"][0] == "PASS"
    assert "/readyz" in by_name["readiness_route"][1]
    assert by_name["l7_websocket"][0] == "PASS"
    assert by_name["gateway_upstream_timeouts"][0] == "PASS"
    assert by_name["async_depends_streamlit"][0] == "PASS"
    assert "disabled" in by_name["async_depends_streamlit"][1]
    assert by_name["gateway_forward_client_headers"][0] == "PASS"
    assert "default" in by_name["gateway_forward_client_headers"][1]


def test_main_invokes_typer_app(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[bool] = []
    monkeypatch.setattr(cli_module, "app", lambda: called.append(True))
    cli_module.main()
    assert called == [True]
