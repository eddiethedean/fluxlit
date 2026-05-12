from __future__ import annotations

from pathlib import Path

from fluxlit import FluxLit, FluxLitTestClient
from fluxlit.testing import apptest_assert_no_errors, apptest_select_page


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
    apptest_assert_no_errors(at)


def test_fluxlit_testclient_streamlit_query_page_opens_admin(
    tmp_path: Path,
    requires_streamlit_apptest,
) -> None:
    module_path = tmp_path / "multi_app2.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "app = FluxLit(title='Multi')\n"
        "@app.api.get('/items')\n"
        "def items():\n"
        "    return [{'name': 'Ada'}]\n"
        "@app.page('/', title='Home')\n"
        "def home(st, client):\n"
        "    st.title('Home Page')\n"
        "@app.page('/admin', title='Admin')\n"
        "def admin(st, client):\n"
        "    st.title('Admin Page')\n",
        encoding="utf-8",
    )

    tc = FluxLitTestClient(FluxLit())
    at = tc.streamlit(
        target="multi_app2:app",
        extra_sys_path=tmp_path,
        query_params={"page": "Admin"},
    )
    assert at.title and at.title[0].value == "Admin Page"
    tc.assert_no_streamlit_exception(at)


def test_fluxlit_testclient_select_page_rerun(
    tmp_path: Path,
    requires_streamlit_apptest,
) -> None:
    module_path = tmp_path / "multi_app3.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "app = FluxLit(title='Multi')\n"
        "@app.page('/', title='Home')\n"
        "def home(st, client):\n"
        "    st.title('Home Page')\n"
        "@app.page('/admin', title='Admin')\n"
        "def admin(st, client):\n"
        "    st.title('Admin Page')\n",
        encoding="utf-8",
    )

    tc = FluxLitTestClient(FluxLit())
    at = tc.streamlit(target="multi_app3:app", extra_sys_path=tmp_path)
    assert at.title and at.title[0].value == "Home Page"
    at2 = tc.select_page(at, "Admin", target="multi_app3:app", extra_sys_path=tmp_path)
    assert at2.title and at2.title[0].value == "Admin Page"
    at3 = apptest_select_page(
        at2,
        tc,
        target="multi_app3:app",
        page="Home",
        extra_sys_path=tmp_path,
    )
    assert at3.title and at3.title[0].value == "Home Page"


def test_apptest_navigation_model_orders_default_page(
    tmp_path: Path,
    requires_streamlit_apptest,
) -> None:
    module_path = tmp_path / "nav_order_app.py"
    module_path.write_text(
        "from fluxlit import FluxLit, NavigationModel\n"
        "app = FluxLit(title='NavOrd')\n"
        "@app.page('/', title='Home')\n"
        "def home(st, client):\n"
        "    st.title('Home Page')\n"
        "@app.page('/z', title='Zed')\n"
        "def zed(st, client):\n"
        "    st.title('Zed Page')\n"
        "app.navigation(NavigationModel(order=('/z', '/')))\n",
        encoding="utf-8",
    )
    at = FluxLitTestClient(FluxLit()).streamlit(target="nav_order_app:app", extra_sys_path=tmp_path)
    assert at.title and at.title[0].value == "Zed Page"


def test_apptest_page_icon_passed_to_st_page(
    tmp_path: Path,
    requires_streamlit_apptest,
) -> None:
    module_path = tmp_path / "icon_app.py"
    module_path.write_text(
        "from fluxlit import FluxLit\n"
        "app = FluxLit(title='Ic')\n"
        "@app.page('/', title='H', icon='🌟')\n"
        "def home(st, client):\n"
        "    st.title('Has Icon')\n",
        encoding="utf-8",
    )
    at = FluxLitTestClient(FluxLit()).streamlit(target="icon_app:app", extra_sys_path=tmp_path)
    assert at.title and at.title[0].value == "Has Icon"
