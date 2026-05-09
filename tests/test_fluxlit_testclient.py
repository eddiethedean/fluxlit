from __future__ import annotations

from pathlib import Path

import pytest

from fluxlit import FluxLit, FluxLitTestClient


def test_fluxlit_testclient_api_healthz() -> None:
    fl = FluxLit(title="T")
    client = FluxLitTestClient(fl)
    res = client.api_get("/healthz")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_fluxlit_testclient_openapi_excludes_healthz() -> None:
    fl = FluxLit(title="T")
    client = FluxLitTestClient(fl)
    paths = client.openapi().get("paths", {})
    assert "/healthz" not in paths


def test_fluxlit_testclient_streamlit_runs(tmp_path: Path) -> None:
    streamlit = pytest.importorskip("streamlit")
    if tuple(int(x) for x in streamlit.__version__.split(".")[:2]) < (1, 30):
        pytest.skip("Streamlit AppTest not available in this version")

    module_path = tmp_path / "demo_tc_app.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n\napp = FluxLit(title='TC App')\n",
        encoding="utf-8",
    )

    fl = FluxLit(title="ignored")
    client = FluxLitTestClient(fl)
    at = client.streamlit(target="demo_tc_app:app", extra_sys_path=tmp_path)
    assert at.title and at.title[0].value == "TC App"
