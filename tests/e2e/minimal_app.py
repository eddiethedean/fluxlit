"""Tiny FluxLit app for Playwright: gateway + Streamlit over a real WebSocket."""

from __future__ import annotations

from fluxlit import FluxLit

app = FluxLit(title="E2E minimal")


@app.page("/", title="Home")
def home(st, client) -> None:  # noqa: ARG001
    st.title("FluxLit E2E")
    st.write("gateway_streamlit_ok")
