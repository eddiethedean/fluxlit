from __future__ import annotations

import pytest

from fluxlit.runtime import (
    _build_streamlit_cmd,
    _build_streamlit_env,
    find_free_port,
    load_fluxlit,
)


def test_load_fluxlit_rejects_bad_target() -> None:
    with pytest.raises(ValueError):
        load_fluxlit("nocolon")


def test_load_fluxlit_rejects_non_fluxlit() -> None:
    with pytest.raises(TypeError):
        load_fluxlit("json:loads")


def test_load_fluxlit_module_not_found() -> None:
    with pytest.raises(ModuleNotFoundError):
        load_fluxlit("definitely_missing_fluxlit_module_xyz:app")


def test_load_fluxlit_missing_attribute(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = tmp_path / "mod_attr.py"
    mod.write_text("x = 1\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    with pytest.raises(AttributeError):
        load_fluxlit("mod_attr:there_is_no_such_attr")


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
