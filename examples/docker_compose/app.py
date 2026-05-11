"""Minimal FluxLit app for the Docker Compose example."""

from __future__ import annotations

from typing import Any

from fluxlit import FluxLit

app = FluxLit(title="Docker Compose demo")


@app.api.get("/hello")
def hello() -> dict[str, str]:
    return {"message": "hello"}


@app.page("/", title="Home")
def home(st: Any, client: Any) -> None:
    st.title("Docker Compose demo")
    st.write(client.get("/hello").json())
