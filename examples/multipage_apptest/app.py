from __future__ import annotations

from fluxlit import FluxLit

app = FluxLit(title="Multipage AppTest Demo")


@app.api.get("/admin/users")
def users() -> list[dict[str, str]]:
    return [{"name": "Ada"}, {"name": "Grace"}]


@app.page("/", title="Home")
def home(st, client) -> None:
    st.title("Home Page")
    st.write("Use stable widget keys for AppTest-friendly pages.")
    st.button("Refresh", key="home_refresh")


@app.page("/admin", title="Admin")
def admin(st, client) -> None:
    st.title("Admin Page")
    rows = client.get("/admin/users").json()
    st.dataframe(rows, key="admin_users_table")
