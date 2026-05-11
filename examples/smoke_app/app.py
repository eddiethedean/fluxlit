"""Canonical FluxLit smoke app used by E2E, proxy, and release checks."""

from __future__ import annotations

from fastapi import Request

from fluxlit import FluxLit

app = FluxLit(title="FluxLit Smoke")


@app.api.get("/smoke")
def smoke() -> dict[str, str]:
    return {"status": "ok", "marker": "fluxlit_smoke_ok"}


@app.api.get("/request-id")
def request_id(request: Request) -> dict[str, str | None]:
    return {"request_id": request.headers.get("x-request-id")}


@app.page("/", title="Home")
def home(st, client) -> None:
    st.title("FluxLit Smoke")
    st.write("fluxlit_smoke_ok")
    st.write(client.get("/smoke").json())
