"""Example FluxLit 0.9 app: PageMeta, Depends, query model, manifest (see docs/streamlit-pages-typing.md)."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

from fluxlit import Depends, FluxLit, NavigationModel, PageMeta, parse_query_params


class Q(BaseModel):
    """Example query string model."""

    tab: str = Field(default="home")


def get_tab_label() -> str:
    return "Demo"


app = FluxLit(title="FluxLit 0.9 Example")


@app.api.get("/ping")
def ping():
    return {"ok": True}


@app.page("/", tags=("demo",), page_meta=PageMeta(page_icon="🚀"))
def home(
    st,
    client,
    label: Annotated[str, Depends(get_tab_label)],
):
    st.title("Roadmap 0.9 example")
    st.caption(label)
    q = parse_query_params(st, Q)
    st.write("tab", q.tab)
    st.write(client.get("/ping").json())


@app.page("/about")
def about(st, client):
    return PageMeta(breadcrumb="About", description="About this demo")


app.navigation(NavigationModel(order=("/about", "/")))
