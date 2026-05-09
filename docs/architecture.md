# Architecture

FluxLit combines **FastAPI** for HTTP APIs and **Streamlit** for interactive UIs behind **one primary port** and one **FluxLit** application object.

## Request path

```text
Client
  → Uvicorn (FluxLit gateway ASGI app)
      ├─ path starts with /api  → FastAPI (prefix stripped inside the app)
      └─ otherwise               → HTTP/WebSocket reverse proxy → Streamlit (subprocess)
```

Streamlit’s own paths (`/_stcore/...`, etc.) appear on the **public** origin because the gateway forwards them transparently.

## Sidecar runtime

1. **Streamlit** runs with `streamlit run` on an ephemeral **localhost** port.
2. **Uvicorn** serves the **gateway** on the user-facing host and port.
3. The gateway forwards non-API traffic to Streamlit, including **WebSockets** required by Streamlit’s protocol.

This matches Streamlit’s supported deployment model, avoids unsupported deep embedding until a stable ASGI embedding story exists, and keeps a clear boundary for testing and operations.

## Streamlit UI routing

- You register pages with {meth}`~fluxlit.app.FluxLit.page` or {meth}`~fluxlit.app.FluxLit.discover_pages`.
- The Streamlit entry script builds `st.Page` entries and runs `st.navigation(...).run()`.
- The HTTP server does not route individual Streamlit pages; **Streamlit** maps URL paths to pages after the gateway forwards the request.

## Principles

- **Pythonic:** explicit, typed surface; ordinary FastAPI and Streamlit in user code.
- **Production-minded:** proxy-friendly (`root_path`, forwarded headers where configured), observable hooks (request ids, optional API access logging).
- **Honest about Streamlit:** subprocess + WebSocket proxy until a native single-process model is proven.

Further product context: see the [architecture and product plan](https://github.com/odosmatthews/fluxlit/blob/main/FLUXLIT_PLAN.md) in the repository.
