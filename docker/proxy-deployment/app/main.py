"""Minimal FluxLit app for Docker proxy smoke tests (nginx + subpath)."""

from __future__ import annotations

from fluxlit import FluxLit

app = FluxLit(title="Proxy smoke")


@app.page("/", title="Home")
def home(st, client) -> None:  # noqa: ARG001
    st.title("Proxy smoke UI")
    st.write("docker_proxy_ok")
