from __future__ import annotations

from pathlib import Path

import pytest


def test_streamlit_entrypoint_renders_info_when_no_pages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    requires_streamlit_apptest,
) -> None:
    """
    Uses Streamlit's built-in AppTest to validate `fluxlit.streamlit_main` renders a
    stable UI when the app defines no pages.
    """
    from streamlit.testing.v1 import AppTest

    # Create a temporary module containing a FluxLit instance with no pages.
    module_path = tmp_path / "demo_app.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n\napp = FluxLit(title='Test App')\n",
        encoding="utf-8",
    )

    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv("FLUXLIT_APP", "demo_app:app")
    monkeypatch.setenv("FLUXLIT_INTERNAL_API_BASE", "http://127.0.0.1:1/api")

    entry = Path(__file__).resolve().parents[1] / "src" / "fluxlit" / "streamlit_main.py"
    at = AppTest.from_file(str(entry)).run()

    assert at.title and at.title[0].value == "Test App"
    assert at.info and "Register UI with" in at.info[0].value


def test_streamlit_entrypoint_runs_registered_page(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    requires_streamlit_apptest,
) -> None:
    from streamlit.testing.v1 import AppTest

    module_path = tmp_path / "demo_pages_app.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n\n"
        "app = FluxLit(title='Paged App')\n\n"
        "@app.page('/')\n"
        "def home(st, client):\n"
        "    st.title('Home')\n"
        "    st.write('Hello from page')\n",
        encoding="utf-8",
    )

    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv("FLUXLIT_APP", "demo_pages_app:app")
    monkeypatch.setenv("FLUXLIT_INTERNAL_API_BASE", "http://127.0.0.1:1/api")

    entry = Path(__file__).resolve().parents[1] / "src" / "fluxlit" / "streamlit_main.py"
    at = AppTest.from_file(str(entry)).run()

    assert at.title and at.title[0].value in {"Home", "Paged App"}
    # Streamlit testing surfaces text elements via `markdown` in many cases.
    found = any("Hello from page" in x.value for x in at.markdown)
    assert found
