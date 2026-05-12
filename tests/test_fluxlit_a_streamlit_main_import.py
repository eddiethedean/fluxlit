"""Import :mod:`fluxlit.streamlit.main` with a fake ``streamlit`` to exercise module logic.

Named ``test_fluxlit_a_*`` so collection runs it **before** ``test_fluxlit_testclient.py``
(any ``AppTest.from_file`` on the Streamlit entry file). Coverage.py stops recording that
path sensibly if AppTest runs first; importing the package module first avoids that.
"""

from __future__ import annotations

import importlib
import sys
import types
from collections.abc import Iterator
from typing import Any
from unittest import mock

import pytest


class StreamlitStop(Exception):
    """Mirrors Streamlit script termination from ``st.stop()``."""


@pytest.fixture
def fake_streamlit(monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    saved_streamlit = sys.modules.pop("streamlit", None)
    saved_main = sys.modules.pop("fluxlit.streamlit.main", None)

    st: Any = types.ModuleType("streamlit")
    st._errors: list[str] = []
    st.set_page_config = mock.Mock()
    st.Page = mock.Mock(return_value=object())
    nav = types.SimpleNamespace()
    nav.run = mock.Mock()
    st.navigation = mock.Mock(return_value=nav)
    st.title = mock.Mock()
    st.info = mock.Mock()

    def error(msg: str) -> None:
        st._errors.append(msg)

    def stop() -> None:
        raise StreamlitStop()

    st.error = error
    st.stop = stop
    st.switch_page = mock.Mock()
    st.query_params = {}
    sb = types.SimpleNamespace()
    sb.caption = mock.Mock()
    st.sidebar = sb

    sys.modules["streamlit"] = st
    try:
        yield st
    finally:
        sys.modules.pop("fluxlit.streamlit.main", None)
        sys.modules.pop("streamlit", None)
        if saved_streamlit is not None:
            sys.modules["streamlit"] = saved_streamlit
        if saved_main is not None:
            sys.modules["fluxlit.streamlit.main"] = saved_main


def test_streamlit_main_errors_when_env_missing(
    fake_streamlit: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FLUXLIT_APP", raising=False)
    sys.modules.pop("fluxlit.streamlit.main", None)
    with pytest.raises(StreamlitStop):
        importlib.import_module("fluxlit.streamlit.main")
    assert fake_streamlit._errors and "FLUXLIT_APP is not set" in fake_streamlit._errors[0]


def test_streamlit_main_invalid_app_spec_raises(
    fake_streamlit: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FLUXLIT_APP", "nocolon")
    sys.modules.pop("fluxlit.streamlit.main", None)
    with pytest.raises(ValueError):
        importlib.import_module("fluxlit.streamlit.main")


def test_streamlit_main_no_pages_shows_hint(
    tmp_path, fake_streamlit: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "sm_np.py").write_text(
        "from fluxlit import FluxLit\napp = FluxLit(title='NP Title')\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv("FLUXLIT_APP", "sm_np:app")
    sys.modules.pop("fluxlit.streamlit.main", None)
    importlib.import_module("fluxlit.streamlit.main")
    fake_streamlit.set_page_config.assert_called_once()
    fake_streamlit.title.assert_called_once_with("NP Title")
    fake_streamlit.info.assert_called_once()
    fake_streamlit.navigation.assert_not_called()


def test_streamlit_main_with_pages_runs_navigation(
    tmp_path, fake_streamlit: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "sm_pg.py").write_text(
        "from fluxlit import FluxLit\n"
        "app = FluxLit(title='PG')\n"
        "@app.page('/')\n"
        "def home(st, client):\n"
        "    st.title('page ran')\n",
        encoding="utf-8",
    )

    class Navigation:
        def __init__(self, pages: list[Any]) -> None:
            self.pages = pages

        def run(self) -> None:
            self.pages[0].fn()

    fake_streamlit.Page = mock.Mock(
        side_effect=lambda fn, **kwargs: types.SimpleNamespace(fn=fn, **kwargs)
    )
    fake_streamlit.navigation = mock.Mock(side_effect=lambda pages: Navigation(pages))
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv("FLUXLIT_APP", "sm_pg:app")
    sys.modules.pop("fluxlit.streamlit.main", None)
    importlib.import_module("fluxlit.streamlit.main")
    fake_streamlit.navigation.assert_called_once()
    fake_streamlit.title.assert_called_once_with("page ran")


def test_streamlit_main_query_page_triggers_switch_page(
    tmp_path, fake_streamlit: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise ``match_nav_page`` + ``st.switch_page`` before ``navigation().run()``."""
    (tmp_path / "sm_nav.py").write_text(
        "from fluxlit import FluxLit\n"
        "app = FluxLit(title='Nav')\n"
        "@app.page('/', title='Home')\n"
        "def home(st, client):\n"
        "    st.title('home')\n"
        "@app.page('/admin', title='Admin')\n"
        "def admin(st, client):\n"
        "    st.title('admin')\n",
        encoding="utf-8",
    )

    switched: list[Any] = []

    def switch_page(pg: Any) -> None:
        switched.append(pg)

    fake_streamlit.query_params = {"page": "Admin"}
    fake_streamlit.switch_page = switch_page

    class Navigation:
        def __init__(self, pages: list[Any]) -> None:
            self.pages = pages

        def run(self) -> None:
            return None

    fake_streamlit.Page = mock.Mock(
        side_effect=lambda fn, **kwargs: types.SimpleNamespace(
            fn=fn,
            title=kwargs.get("title"),
            url_path=kwargs.get("url_path"),
            icon=kwargs.get("icon"),
        )
    )
    fake_streamlit.navigation = mock.Mock(side_effect=lambda pages: Navigation(pages))
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv("FLUXLIT_APP", "sm_nav:app")
    sys.modules.pop("fluxlit.streamlit.main", None)
    importlib.import_module("fluxlit.streamlit.main")

    assert len(switched) == 1
    assert switched[0].url_path == "admin"
    fake_streamlit.navigation.assert_called_once()
