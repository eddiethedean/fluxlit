# FluxLit — Product & Architecture Plan

This document is the **product and architecture** companion to the [development roadmap](ROADMAP.md). It describes what FluxLit (`fluxlit`) is for, how the runtime is structured today, and where it is headed.

---

## Vision

FluxLit is a production-grade Python application runtime that unifies **FastAPI** and **Streamlit** into one developer experience: one app object, one primary port, and a clear split between API traffic and UI traffic.

It exists to reduce friction when combining:

- FastAPI for HTTP APIs, validation, and OpenAPI
- Streamlit for data and admin UIs
- Future: shared authentication, configuration, and deployment patterns

FluxLit should feel natural to Python teams building internal tools and data products—without giving up operational rigor.

---

## Core principles

### 1. One app

Users work with:

- A single **`FluxLit`** instance exposing **`.api`** (FastAPI)
- Declarative **`@app.page`** handlers for Streamlit, wired through `st.navigation`
- One **gateway** URL for browsers (APIs under **`/api`**)

They should not have to manually coordinate public ports, CORS between arbitrary origins for same-app traffic, or bespoke nginx configs for local development.

### 2. Production first

FluxLit is not only a demo launcher. Over time it should support:

- Reverse proxies (`root_path`, forwarded headers)
- Container and Kubernetes-friendly process model
- Structured logging, health/readiness, and metrics hooks
- Authentication patterns used in enterprises (forward auth, JWT, OIDC)

**Today (0.1.x):** the sidecar gateway and `/api` prefix are the foundation; auth, metrics, and official container recipes are **not** complete—see the roadmap.

### 3. Pythonic surface

- Typed, explicit APIs
- Minimal magic; user code should remain ordinary FastAPI and Streamlit
- Configuration via **pydantic-settings** (`FLUXLIT_*`, `.env`)

---

## Architecture (implemented)

### Request path

```text
Client
  → Uvicorn (FluxLit gateway ASGI app)
      ├─ path starts with /api  → FastAPI sub-application (prefix stripped)
      └─ otherwise               → HTTP/WebSocket reverse proxy → Streamlit (subprocess)
```

Streamlit continues to use its normal URL space (`/_stcore/...`, etc.) on the **public** origin because those paths are proxied transparently.

### Runtime strategy: sidecar (Phase 1)

**Current approach**

1. **Streamlit** is started with `streamlit run` on an ephemeral **localhost** port.
2. **Uvicorn** runs the **gateway** on the user-facing host/port.
3. The gateway forwards non-API traffic to Streamlit, including **WebSockets** required by Streamlit’s protocol.

**Why**

- Matches Streamlit’s supported deployment model today
- Avoids unsupported deep embedding until Streamlit exposes a stable ASGI embedding story
- Keeps a clear boundary for testing and operations

### Future: native ASGI (research)

The [roadmap](ROADMAP.md) Phase 5 covers optional single-process or embedded modes if Streamlit and ASGI semantics align without breaking websocket behavior.

### Browser refresh and session continuity (no cookies)

Full page reload can drop Streamlit’s in-process session unless state is **rehydrated** from somewhere else. FluxLit’s preferred direction—documented as **Phase 2 follow-on** in the [roadmap](ROADMAP.md)—is an **opaque token in the URL query string** (`st.query_params`) plus a **server-side store** (memory for single-worker dev, Redis or similar for production). That avoids **HTTP cookies** while keeping refresh continuity explicit and shareable links treated as secrets over HTTPS.

---

## Package modules (`fluxlit`)

| Area | Module | Responsibility |
|------|--------|----------------|
| App | `fluxlit.app` | `FluxLit`, `@app.page`, FastAPI instance |
| CLI | `fluxlit.cli` | `fluxlit dev`, `run`, `new`, `doctor`, `build` |
| Config | `fluxlit.config` | `FluxlitSettings` / `FLUXLIT_*` |
| Project file | `fluxlit.project_config` | `fluxlit.toml` / `[tool.fluxlit]` defaults |
| Client | `fluxlit.client` | `ApiClient` for server-side calls into `/api` |
| Testing | `fluxlit.testing` | `FluxLitTestClient` (API gateway TestClient + Streamlit AppTest helper); repo CI splits fast vs `slow`, coverage artifact, E2E, proxy smoke (see `docs/testing.md`) |
| Gateway | `fluxlit.gateway` | ASGI dispatch and reverse proxy |
| Logging | `fluxlit.logging_context` | Request id context for gateway / API |
| Runtime | `fluxlit.runtime` | Load `FluxLit` by import path, spawn Streamlit, run Uvicorn |
| Streamlit | `fluxlit.streamlit_main` | Streamlit script; reads `FLUXLIT_APP`, builds navigation |
| Helpers | `fluxlit.api`, `fluxlit.auth` | Router helpers; auth placeholders |

`fluxlit build` emits starter container files; a dedicated `fluxlit.deploy` module and richer K8s examples remain future work.

---

## Authentication (directional)

**Target modes** (see roadmap Phase 3):

- **Trusted headers** from a front proxy (SSO, corporate gateways)
- **JWT** bearer validation for APIs; propagation of claims to UI where feasible
- **Sessions** (signed cookies, optional external store)
- **OAuth2/OIDC** via providers (Azure AD, Okta, Google, GitHub, etc.)

**Today:** `fluxlit.auth` may expose small helpers; end-to-end auth is **application responsibility** until dedicated FluxLit middleware and Streamlit session bridging land.

---

## Deployment targets (goals)

**Aspirational support matrix**

- Linux VMs, systemd
- Docker and Kubernetes
- Uvicorn (primary) / other ASGI servers where compatible
- Posit Workbench / Posit Connect (patterns TBD; may require vendor-specific docs)

**Today:** run `fluxlit run` behind your own reverse proxy; tune `FLUXLIT_ROOT_PATH` and forwarded headers per your environment.

---

## Risks and mitigations

### Streamlit embedding

Streamlit is not designed as a generic ASGI “mount” in all versions. **Mitigation:** sidecar subprocess + gateway proxy; abstract the boundary so a future native mode can swap behind the same `FluxLit` API where possible.

### WebSockets

Streamlit depends on reliable WebSocket behavior. **Mitigation:** gateway implements WebSocket proxying; add automated tests and soak notes as the project matures (see roadmap testing strategy).

### Operational complexity

Two processes (gateway + Streamlit) require clean **shutdown** and observability. **Mitigation:** document signals and timeouts; improve runtime supervision in Phase 1 hardening.

---

## Long-term vision

FluxLit can become a default way to ship **Python-first** full-stack apps that blend APIs and interactive UIs—especially in data, ML, and internal platforms—without adopting a separate Node frontend for every tool.

Broader possibilities (post–1.0): plugins, shared UI patterns, background jobs, realtime bridges between FastAPI and Streamlit.

---

## Related documentation

- [README](README.md) — install, quick start, CLI, configuration
- [ROADMAP.md](ROADMAP.md) — phased delivery and current status
