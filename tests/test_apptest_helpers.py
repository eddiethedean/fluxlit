from __future__ import annotations

import types

import pytest

from fluxlit import FluxLit
from fluxlit.testing import (
    FluxLitTestClient,
    apptest_assert_no_errors,
    assert_no_streamlit_exception,
)


def test_apptest_assert_no_errors_passes() -> None:
    at = types.SimpleNamespace(exception=[], error=[])
    apptest_assert_no_errors(at)
    assert_no_streamlit_exception(at)


def test_apptest_assert_no_errors_raises_on_exception() -> None:
    bad = types.SimpleNamespace(value="boom")
    at = types.SimpleNamespace(exception=[bad], error=[])
    with pytest.raises(AssertionError, match="st.exception"):
        apptest_assert_no_errors(at)


def test_apptest_assert_no_errors_raises_on_error() -> None:
    bad = types.SimpleNamespace(value="user visible")
    at = types.SimpleNamespace(exception=[], error=[bad])
    with pytest.raises(AssertionError, match="st.error"):
        apptest_assert_no_errors(at)


def test_fluxlit_test_client_assert_no_streamlit_exception_delegates() -> None:
    called: dict[str, object] = {}

    def fake(at: object) -> None:
        called["at"] = at

    at = object()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("fluxlit.testing.apptest_assert_no_errors", fake)
    try:
        FluxLitTestClient(FluxLit()).assert_no_streamlit_exception(at)
    finally:
        monkeypatch.undo()
    assert called["at"] is at


def test_fluxlit_test_client_select_page_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake(
        at: object,
        client: FluxLitTestClient,
        *,
        target: str,
        page: str,
        internal_api_base: str | None = None,
        extra_sys_path: object = None,
        page_key: str = "page",
        page_overrides: dict[str, object] | None = None,
    ) -> str:
        del page_overrides
        captured.update(
            {
                "at": at,
                "client": client,
                "target": target,
                "page": page,
                "page_key": page_key,
            }
        )
        return "ok"

    monkeypatch.setattr("fluxlit.testing.apptest_select_page", fake)
    tc = FluxLitTestClient(FluxLit())
    assert tc.select_page("atobj", "P", target="t:app", page_key="tab") == "ok"
    assert captured["at"] == "atobj"
    assert captured["client"] is tc
    assert captured["target"] == "t:app"
    assert captured["page"] == "P"
    assert captured["page_key"] == "tab"
