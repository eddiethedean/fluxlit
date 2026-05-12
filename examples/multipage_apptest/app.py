from typing import Any

from fluxlit import FluxLit
from fluxlit.client import ApiClient

app = FluxLit(title="Multipage AppTest Demo")


@app.api.get("/admin/users")
def users() -> list[dict[str, str]]:
    return [{"name": "Ada"}, {"name": "Grace"}]


@app.page("/", title="Home")
def home(st: Any, client: ApiClient) -> None:
    st.title("Home Page")
    st.write("Use stable widget keys for AppTest-friendly pages.")
    st.button("Refresh", key="home_refresh")


@app.page("/admin", title="Admin")
def admin(st: Any, client: ApiClient) -> None:
    st.title("Admin Page")
    rows = client.get("/admin/users").json()
    st.dataframe(rows, key="admin_users_table")
