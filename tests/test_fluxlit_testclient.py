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


def test_fluxlit_testclient_api_property_hits_gateway_with_mount() -> None:
    fl = FluxLit(title="T")
    tc = FluxLitTestClient(fl).with_root_path("/wb")
    res = tc.api.get("/wb/api/healthz")
    assert res.status_code == 200


def test_fluxlit_testclient_with_root_path_api_get() -> None:
    fl = FluxLit(title="T")
    tc = FluxLitTestClient(fl).with_root_path("/workbench")
    res = tc.api_get("/healthz")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_fluxlit_testclient_api_get_per_call_root_path() -> None:
    fl = FluxLit(title="T")
    tc = FluxLitTestClient(fl)
    res = tc.api_get("/healthz", root_path="/wb")
    assert res.status_code == 200


def test_fluxlit_testclient_assert_docs_available() -> None:
    FluxLitTestClient(FluxLit(title="T")).assert_docs_available()


def test_fluxlit_testclient_assert_docs_available_with_root_path_kwarg() -> None:
    FluxLitTestClient(FluxLit(title="T")).assert_docs_available(root_path="/wb")


def test_fluxlit_testclient_assert_docs_available_under_root_mount() -> None:
    FluxLitTestClient(FluxLit(title="T")).with_root_path("/wb").assert_docs_available()


def test_fluxlit_testclient_assert_docs_available_fails_without_docs() -> None:
    fl = FluxLit(title="T", fastapi_kwargs={"docs_url": None, "redoc_url": None})
    tc = FluxLitTestClient(fl)
    with pytest.raises(AssertionError, match="Swagger UI not available"):
        tc.assert_docs_available()


def test_fluxlit_testclient_assert_docs_invalid_openapi_payload() -> None:
    fl = FluxLit(title="T")

    def fake_get(self: FluxLitTestClient, path: str, **kwargs: Any) -> Any:
        class R:
            status_code = 200

            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, object]:
                return {"paths": {}}

        return R()

    with patch.object(FluxLitTestClient, "api_get", fake_get):
        with pytest.raises(AssertionError, match="OpenAPI JSON"):
            FluxLitTestClient(fl).assert_docs_available()


def test_fluxlit_testclient_assert_docs_unexpected_docs_status() -> None:
    fl = FluxLit(title="T")

    def fake_get(self: FluxLitTestClient, path: str, **kwargs: Any) -> Any:
        class R:
            def __init__(self, code: int) -> None:
                self.status_code = code

            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, str]:
                return {"openapi": "3.1.0", "paths": {}}

        if path.endswith("/openapi.json"):
            return R(200)
        return R(418)

    with patch.object(FluxLitTestClient, "api_get", fake_get):
        with pytest.raises(AssertionError, match="Unexpected GET /docs"):
            FluxLitTestClient(fl).assert_docs_available()


def test_fluxlit_testclient_streamlit_query_params(
    tmp_path: Path,
    requires_streamlit_apptest,
) -> None:
    module_path = tmp_path / "qp_tc_app.py"
    module_path.write_text(
        "from fluxlit import FluxLit, query_params\n\n"
        "app = FluxLit(title='QP App')\n\n"
        "@app.page('/')\n"
        "def home(st, client):\n"
        "    p = query_params(st)\n"
        "    st.text_input('t', value=p.get('token', ''), key='tkey')\n",
        encoding="utf-8",
    )
    fl = FluxLit(title="x")
    at = FluxLitTestClient(fl).streamlit(
        target="qp_tc_app:app",
        extra_sys_path=tmp_path,
        query_params={"token": "from-query"},
    )
    assert at.text_input(key="tkey").value == "from-query"


def test_fluxlit_testclient_streamlit_page_overrides(
    tmp_path: Path,
    requires_streamlit_apptest,
) -> None:
    module_path = tmp_path / "ov_tc_app.py"
    module_path.write_text(
        "from typing import Annotated\n"
        "from fluxlit import FluxLit, Header\n\n"
        "app = FluxLit(title='OV App')\n\n"
        "@app.page('/')\n"
        "def home(st, client, h: Annotated[str | None, Header('x-override')]):\n"
        "    st.title(h or 'none')\n",
        encoding="utf-8",
    )
    fl = FluxLit(title="x")
    at = FluxLitTestClient(fl).streamlit(
        target="ov_tc_app:app",
        extra_sys_path=tmp_path,
        page_overrides={"h": "injected"},
    )
    assert at.title and at.title[0].value == "injected"


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
