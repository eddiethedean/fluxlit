from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from fastapi import Request

from fluxlit import FluxLit, FluxLitTestClient


def test_fluxlit_testclient_api_post_json() -> None:
    fl = FluxLit(title="T")

    @fl.api.post("/items")
    async def add_item(request: Request) -> dict[str, str]:
        data = await request.json()
        return {"id": str(data.get("name", ""))}

    client = FluxLitTestClient(fl)
    res = client.api_post("/items", json={"name": "x"})
    assert res.status_code == 200
    assert res.json() == {"id": "x"}


def test_fluxlit_testclient_api_healthz() -> None:
    fl = FluxLit(title="T")
    client = FluxLitTestClient(fl)
    res = client.api_get("/healthz")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_fluxlit_testclient_custom_api_prefix() -> None:
    fl = FluxLit(title="T")

    @fl.api.get("/hello")
    def hello() -> dict[str, str]:
        return {"hi": "there"}

    client = FluxLitTestClient(fl, api_prefix="/v1")
    res = client.api_get("/hello")
    assert res.status_code == 200
    assert res.json() == {"hi": "there"}


def test_fluxlit_testclient_openapi_excludes_healthz() -> None:
    fl = FluxLit(title="T")
    client = FluxLitTestClient(fl)
    paths = client.openapi().get("paths", {})
    assert "/healthz" not in paths
    assert "/readyz" not in paths


def test_fluxlit_testclient_openapi_type_error_when_not_object() -> None:
    fl = FluxLit(title="T")

    def bad_api_get(self: FluxLitTestClient, path: str, **kwargs: Any) -> Any:
        class _Resp:
            def json(self) -> list[int]:
                return [1, 2]

        return _Resp()

    with patch.object(FluxLitTestClient, "api_get", bad_api_get):
        client = FluxLitTestClient(fl)
        with pytest.raises(TypeError, match="JSON object"):
            client.openapi()


def test_fluxlit_testclient_streamlit_runs(
    tmp_path: Path,
    requires_streamlit_apptest,
) -> None:
    module_path = tmp_path / "demo_tc_app.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n\napp = FluxLit(title='TC App')\n",
        encoding="utf-8",
    )

    fl = FluxLit(title="ignored")
    client = FluxLitTestClient(fl)
    at = client.streamlit(target="demo_tc_app:app", extra_sys_path=tmp_path)
    assert at.title and at.title[0].value == "TC App"
