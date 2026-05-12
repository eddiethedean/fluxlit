from __future__ import annotations

from pathlib import Path

from fluxlit import FluxLit, FluxLitTestClient


def test_fluxlit_testclient_streamlit_multipage_smoke(
    tmp_path: Path,
    requires_streamlit_apptest,
) -> None:
    module_path = tmp_path / "multi_app.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "app = FluxLit(title='Multi')\n"
        "@app.api.get('/items')\n"
        "def items():\n"
        "    return [{'name': 'Ada'}]\n"
        "@app.page('/', title='Home')\n"
        "def home(st, client):\n"
        "    st.title('Home Page')\n"
        "    st.button('Refresh', key='home_refresh')\n"
        "@app.page('/admin', title='Admin')\n"
        "def admin(st, client):\n"
        "    st.title('Admin Page')\n"
        "    st.dataframe(client.get('/items').json(), key='admin_items_table')\n",
        encoding="utf-8",
    )

    at = FluxLitTestClient(FluxLit()).streamlit(target="multi_app:app", extra_sys_path=tmp_path)
    assert at.title and at.title[0].value == "Home Page"
