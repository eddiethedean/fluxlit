from __future__ import annotations

import pytest

from fluxlit.runtime import (
    _build_streamlit_cmd,
    _build_streamlit_env,
    _inject_public_root_path,
    find_free_port,
    internal_api_base_url,
    load_fluxlit,
)


def test_load_fluxlit_rejects_bad_target() -> None:
    with pytest.raises(ValueError):
        load_fluxlit("nocolon")


def test_load_fluxlit_rejects_non_fluxlit() -> None:
    with pytest.raises(TypeError):
        load_fluxlit("json:loads")


def test_load_fluxlit_module_not_found() -> None:
    with pytest.raises(ModuleNotFoundError, match="PYTHONPATH"):
        load_fluxlit("definitely_missing_fluxlit_module_xyz:app")


def test_load_fluxlit_missing_attribute(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = tmp_path / "mod_attr.py"
    mod.write_text("x = 1\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    with pytest.raises(AttributeError):
        load_fluxlit("mod_attr:there_is_no_such_attr")


def test_internal_api_base_url_maps_inaddr_any_to_loopback() -> None:
    assert internal_api_base_url(bind_host="0.0.0.0", port=8000, api_mount_path="/api") == (
        "http://127.0.0.1:8000/api"
    )
    assert internal_api_base_url(bind_host="", port=9000, api_mount_path="/api") == (
        "http://127.0.0.1:9000/api"
    )
    assert internal_api_base_url(bind_host="::", port=8000, api_mount_path="/api") == (
        "http://127.0.0.1:8000/api"
    )


def test_internal_api_base_url_brackets_ipv6() -> None:
    assert internal_api_base_url(bind_host="::1", port=8000, api_mount_path="/api") == (
        "http://[::1]:8000/api"
    )
    assert internal_api_base_url(bind_host="[::1]", port=8000, api_mount_path="/v1") == (
        "http://[::1]:8000/v1"
    )


def test_internal_api_base_url_plain_hostnames() -> None:
    assert internal_api_base_url(bind_host="127.0.0.1", port=1, api_mount_path="/api") == (
        "http://127.0.0.1:1/api"
    )
    assert internal_api_base_url(bind_host="localhost", port=8000, api_mount_path="api") == (
        "http://localhost:8000/api"
    )


def test_find_free_port_returns_ephemeral_port() -> None:
    a = find_free_port()
    b = find_free_port()
    assert 1024 < a < 65536
    assert 1024 < b < 65536
    assert a != b


def test_build_streamlit_env_sets_fluxlit_vars() -> None:
    env = _build_streamlit_env(
        target="m:app",
        api_prefix="/api",
        internal_api_base="http://127.0.0.1:8000/api",
    )
    assert env["FLUXLIT_APP"] == "m:app"
    assert env["FLUXLIT_API_PREFIX"] == "/api"
    assert env["FLUXLIT_INTERNAL_API_BASE"] == "http://127.0.0.1:8000/api"


def test_build_streamlit_cmd_contains_port(tmp_path) -> None:
    runner = tmp_path / "streamlit_main.py"
    cmd = _build_streamlit_cmd(runner=runner, port=1234)
    assert "streamlit" in cmd
    assert "run" in cmd
    assert str(runner) in cmd
    assert "1234" in cmd
    assert "--server.address" in cmd
    assert "127.0.0.1" in cmd
    assert "--server.enableXsrfProtection" in cmd
    assert "--server.enableCORS" in cmd
    assert cmd.count("false") >= 2


def test_build_streamlit_cmd_adds_base_url_path(tmp_path) -> None:
    runner = tmp_path / "streamlit_main.py"
    cmd = _build_streamlit_cmd(runner=runner, port=1234, base_url_path="/connect/app123")
    assert "--server.baseUrlPath" in cmd
    assert cmd[cmd.index("--server.baseUrlPath") + 1] == "/connect/app123"


def test_public_mount_path_prefers_root_path() -> None:
    from fluxlit.config import FluxlitSettings

    s = FluxlitSettings(root_path="/a", streamlit_public_path="/b")
    assert s.public_mount_path() == "/a"


def test_public_mount_path_falls_back_to_streamlit_public() -> None:
    from fluxlit.config import FluxlitSettings

    s = FluxlitSettings(root_path="", streamlit_public_path="/legacy")
    assert s.public_mount_path() == "/legacy"


@pytest.mark.asyncio
async def test_inject_public_root_path_fills_empty_asgi_root_path() -> None:
    """Uvicorn runs with root_path=''; wrapper supplies the browser mount for OpenAPI."""
    captured: dict[str, str] = {}

    async def inner(scope, receive, send):  # noqa: ARG001
        captured["root_path"] = str(scope.get("root_path") or "")

    app = _inject_public_root_path(inner, "/myapp")
    await app({"type": "http", "path": "/api/healthz", "root_path": ""}, None, None)  # type: ignore[arg-type]
    assert captured["root_path"] == "/myapp"


@pytest.mark.asyncio
async def test_inject_public_root_path_noop_when_root_path_already_set() -> None:
    captured: dict[str, str] = {}

    async def inner(scope, receive, send):  # noqa: ARG001
        captured["root_path"] = str(scope.get("root_path") or "")

    app = _inject_public_root_path(inner, "/myapp")
    await app(
        {"type": "http", "path": "/x", "root_path": "/custom"},
        None,
        None,  # type: ignore[arg-type]
    )
    assert captured["root_path"] == "/custom"
