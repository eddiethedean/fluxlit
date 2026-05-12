from __future__ import annotations

import sys
import types

import pytest

from fluxlit import FluxLit, streamlit_main_path
from fluxlit.testing import FluxLitTestClient, _maybe_syspath, _patched_env


def test_fluxlit_test_client_openapi_rejects_non_object(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FluxLitTestClient(FluxLit())
    monkeypatch.setattr(
        FluxLitTestClient,
        "api_get",
        lambda self, path: types.SimpleNamespace(json=lambda: []),
    )
    with pytest.raises(TypeError, match="OpenAPI response"):
        client.openapi()


def test_fluxlit_test_client_api_helpers_and_openapi_success() -> None:
    app = FluxLit()

    @app.api.get("/items")
    def items() -> dict[str, str]:
        return {"ok": "get"}

    @app.api.post("/items")
    def post_items() -> dict[str, str]:
        return {"ok": "post"}

    client = FluxLitTestClient(app)
    assert client.api_get("items").json() == {"ok": "get"}
    assert client.api_post("/items").json() == {"ok": "post"}
    assert isinstance(client.openapi(), dict)


def test_streamlit_main_path_points_to_packaged_entry() -> None:
    path = streamlit_main_path()
    assert path.name == "main.py"
    assert path.parent.name == "streamlit"
    assert path.is_file()


def test_fluxlit_test_client_streamlit_rejects_old_streamlit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_streamlit = types.SimpleNamespace(__version__="1.29.0")
    monkeypatch.setitem(sys.modules, "streamlit", fake_streamlit)
    with pytest.raises(RuntimeError, match="AppTest"):
        FluxLitTestClient(FluxLit()).streamlit(target="x:app")


def test_fluxlit_test_client_streamlit_patches_env_and_syspath(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_streamlit = types.SimpleNamespace(__version__="1.30.0")

    class FakeAppTest:
        captured_path = ""

        @classmethod
        def from_file(cls, path: str) -> FakeAppTest:
            cls.captured_path = path
            return cls()

        def run(self) -> dict[str, object]:
            import os

            return {
                "app": os.environ["FLUXLIT_APP"],
                "base": os.environ["FLUXLIT_INTERNAL_API_BASE"],
                "prefix": os.environ["FLUXLIT_API_PREFIX"],
                "syspath0": sys.path[0],
            }

    monkeypatch.setitem(sys.modules, "streamlit", fake_streamlit)
    monkeypatch.setitem(sys.modules, "streamlit.testing", types.ModuleType("streamlit.testing"))
    testing_v1 = types.ModuleType("streamlit.testing.v1")
    testing_v1.AppTest = FakeAppTest
    monkeypatch.setitem(sys.modules, "streamlit.testing.v1", testing_v1)
    result = FluxLitTestClient(FluxLit(), api_prefix="/v1").streamlit(
        target="demo:app",
        internal_api_base="http://test/api",
        extra_sys_path=tmp_path,
    )
    assert result["app"] == "demo:app"
    assert result["base"] == "http://test/api"
    assert result["prefix"] == "/v1"
    assert result["syspath0"] == str(tmp_path)
    assert FakeAppTest.captured_path == str(streamlit_main_path())


def test_patched_env_restores_existing_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLUXLIT_TEST_ENV", "old")
    with _patched_env({"FLUXLIT_TEST_ENV": "new"}):
        import os

        assert os.environ["FLUXLIT_TEST_ENV"] == "new"
    import os

    assert os.environ["FLUXLIT_TEST_ENV"] == "old"


def test_maybe_syspath_noop_when_extra_none() -> None:
    before = list(sys.path)
    with _maybe_syspath(None):
        assert sys.path == before
