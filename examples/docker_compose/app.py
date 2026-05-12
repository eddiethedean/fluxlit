"""Minimal FluxLit app for the Docker Compose example."""

from typing import Any

from fluxlit import FluxLit
from fluxlit.client import ApiClient

app = FluxLit(title="Docker Compose demo")


@app.api.get("/hello")
def hello() -> dict[str, str]:
    return {"message": "hello"}


@app.page("/", title="Home")
def home(st: Any, client: ApiClient) -> None:
    st.title("Docker Compose demo")
    st.write(client.get("/hello").json())
