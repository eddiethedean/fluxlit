from __future__ import annotations

import pytest

from fluxlit.runtime import _build_streamlit_cmd, _build_streamlit_env, load_fluxlit


def test_load_fluxlit_rejects_bad_target() -> None:
    with pytest.raises(ValueError):
        load_fluxlit("nocolon")


def test_load_fluxlit_rejects_non_fluxlit() -> None:
    with pytest.raises(TypeError):
        load_fluxlit("json:loads")


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
