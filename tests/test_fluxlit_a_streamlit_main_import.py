"""Import :mod:`fluxlit.streamlit_main` with a fake ``streamlit`` to exercise module logic.

Named ``test_fluxlit_a_*`` so collection runs it **before** ``test_fluxlit_testclient.py``
(any ``AppTest.from_file`` on ``streamlit_main.py``). Coverage.py stops recording that
path sensibly if AppTest runs first; importing the package module first avoids that.
"""

from __future__ import annotations

import importlib
import sys
import types
from collections.abc import Iterator
from unittest import mock

import pytest


class StreamlitStop(Exception):
    """Mirrors Streamlit script termination from ``st.stop()``."""


@pytest.fixture
def fake_streamlit(monkeypatch: pytest.MonkeyPatch) -> Iterator[types.SimpleNamespace]:
    saved_streamlit = sys.modules.pop("streamlit", None)
    saved_main = sys.modules.pop("fluxlit.streamlit_main", None)

    st = types.SimpleNamespace()
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

    sys.modules["streamlit"] = st
    try:
        yield st
    finally:
        sys.modules.pop("fluxlit.streamlit_main", None)
        sys.modules.pop("streamlit", None)
        if saved_streamlit is not None:
            sys.modules["streamlit"] = saved_streamlit
        if saved_main is not None:
            sys.modules["fluxlit.streamlit_main"] = saved_main


def test_streamlit_main_errors_when_env_missing(
    fake_streamlit: types.SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FLUXLIT_APP", raising=False)
    sys.modules.pop("fluxlit.streamlit_main", None)
    with pytest.raises(StreamlitStop):
        importlib.import_module("fluxlit.streamlit_main")
    assert fake_streamlit._errors and "FLUXLIT_APP is not set" in fake_streamlit._errors[0]


def test_streamlit_main_invalid_app_spec_raises(
    fake_streamlit: types.SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FLUXLIT_APP", "nocolon")
    sys.modules.pop("fluxlit.streamlit_main", None)
    with pytest.raises(ValueError):
        importlib.import_module("fluxlit.streamlit_main")


def test_streamlit_main_no_pages_shows_hint(
    tmp_path, fake_streamlit: types.SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "sm_np.py").write_text(
        "from fluxlit import FluxLit\napp = FluxLit(title='NP Title')\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv("FLUXLIT_APP", "sm_np:app")
    sys.modules.pop("fluxlit.streamlit_main", None)
    importlib.import_module("fluxlit.streamlit_main")
    fake_streamlit.set_page_config.assert_called_once()
    fake_streamlit.title.assert_called_once_with("NP Title")
    fake_streamlit.info.assert_called_once()
    fake_streamlit.navigation.assert_not_called()


def test_streamlit_main_with_pages_runs_navigation(
    tmp_path, fake_streamlit: types.SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "sm_pg.py").write_text(
        "from fluxlit import FluxLit\n"
        "app = FluxLit(title='PG')\n"
        "@app.page('/')\n"
        "def home(st, client):\n"
        "    pass\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv("FLUXLIT_APP", "sm_pg:app")
    sys.modules.pop("fluxlit.streamlit_main", None)
    importlib.import_module("fluxlit.streamlit_main")
    fake_streamlit.navigation.assert_called_once()
    fake_streamlit.navigation.return_value.run.assert_called_once()
