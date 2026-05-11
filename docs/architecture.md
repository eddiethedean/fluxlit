# Architecture

Read this page when you want a **mental model** of how a single browser request becomes either a FastAPI handler or Streamlit traffic.

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

### Processes and environment

| Role | Process | Listens on |
|------|---------|------------|
| Gateway | Uvicorn worker(s) | Public `host:port` (e.g. `0.0.0.0:8000`) |
| Streamlit | Child of the runtime | Ephemeral **localhost** port (not exposed directly) |

The runtime sets **`FLUXLIT_*`** variables so Streamlit’s entry script knows the import target, API prefix, internal API base URL, and (from the parent) where to reach the Streamlit HTTP server for readiness checks. See {ref}`runtime-env`.

### Operational endpoints

Under the configured API mount (default **`/api`**), the inner app exposes **`/healthz`** (liveness) and **`/readyz`** (readiness vs Streamlit). Public URLs are typically **`/api/healthz`** and **`/api/readyz`**.

These routes are registered with **`include_in_schema=False`** so they do not appear in Swagger/OpenAPI; your own API surface stays clean.

## Streamlit UI routing

- You register pages with {meth}`~fluxlit.app.FluxLit.page` or {meth}`~fluxlit.app.FluxLit.discover_pages`.
- The Streamlit entry script builds `st.Page` entries and runs `st.navigation(...).run()`.
- The HTTP server does not route individual Streamlit pages; **Streamlit** maps URL paths to pages after the gateway forwards the request.

## Principles

- **Pythonic:** explicit, typed surface; ordinary FastAPI and Streamlit in user code.
- **Production-minded:** proxy-friendly (`root_path`, forwarded headers where configured), observable hooks (request ids forwarded to Streamlit on proxied HTTP/WebSocket, optional API and **gateway** access logging, readiness via `/api/readyz`), and tunable gateway timeouts, body limits, and upstream `httpx` pool behavior via {class}`~fluxlit.config.FluxlitSettings` / `FLUXLIT_*` (see {doc}`configuration`).
- **Honest about Streamlit:** subprocess + WebSocket proxy until a native single-process model is proven.

Further product context: see the [architecture and product plan](https://github.com/eddiethedean/fluxlit/blob/main/PLAN.md) in the repository.

## Automated tests

Gateway routing, HTTP/WebSocket proxying, `root_path`, readiness (`/api/readyz`), and auth helpers are covered by Pytest (fast matrix, optional `slow` subprocess checks, Playwright E2E, and Docker-based proxy smoke). See {doc}`testing` and {doc}`observability`.
