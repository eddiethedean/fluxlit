# FluxLit — Development Roadmap

This document tracks **FluxLit** (`fluxlit` on PyPI): a unified FastAPI + Streamlit runtime. Phases are ordered for risk reduction: prove the gateway, harden operations, then deepen product features.

---

## Current status (0.1.x)

**Done**

- **Foundation:** `src/` layout, `pyproject.toml`, Hatchling build, Ruff, Mypy (strict), Pytest.
- **Unified dev/prod entry:** `fluxlit dev` / `fluxlit run` with a single public port; Streamlit runs in a managed subprocess with an internal port.
- **Gateway:** configurable API prefix (default `/api`); path prefix stripped for the inner FastAPI app; HTTP + WebSocket proxy to Streamlit for all other paths.
- **App model:** `FluxLit` holds `FastAPI` on `.api`, `@app.page` registers Streamlit pages; `ApiClient` for server-side calls with `FLUXLIT_INTERNAL_API_BASE`.
- **Scaffold:** `fluxlit new <name>` minimal app.
- **Tests:** gateway routing / OpenAPI prefix, page registration, `load_fluxlit` validation, CLI tests, ApiClient tests, Streamlit AppTest, FluxLit-native test client.

**Gaps vs “production”**

- CI workflow (Linux / macOS / Windows matrix) exists; expand with higher-signal integration tests over time.
- Reload is gateway-only (`fluxlit dev --reload`); Streamlit lifecycle on reload is not orchestrated.
- Auth, metrics, and hardened Docker/K8s beyond `fluxlit build` templates are not implemented.
- **Browser refresh continuity** for Streamlit (cookie-free, URL + server store) is specified under **Phase 2 follow-on** in this file but not implemented yet.

---

## Phase 0 — Foundation (complete)

### Goals

- Reproducible packaging, quality gates, and a clear module boundary for runtime vs user app.

### Deliverables

| Item                         | Status |
|-----------------------------|--------|
| Repository + `pyproject`    | Done   |
| Lint + format (Ruff)        | Done   |
| Typing (Mypy strict)        | Done   |
| Tests (Pytest)              | Done   |
| CI (install, test, lint)    | Done   |
| Contributor docs / changelog | Done   |

### Stack (locked for 0.x)

FastAPI, Starlette, Uvicorn, Streamlit, Pydantic Settings, Typer, AnyIO, httpx, websockets.

---

## Phase 1 — Unified runtime MVP (mostly complete)

### Goals

- One **public** port for browser traffic; predictable routing; safe teardown of child processes.

### Shipped

- `fluxlit dev [target]` / `fluxlit run [target]` (`target` default `app:app`).
- Subprocess orchestration for Streamlit + Uvicorn gateway.
- Reverse proxy behavior in-process (HTTP + WebSocket) to Streamlit.

### Remaining / hardening

- **Graceful shutdown:** ensure Streamlit and Uvicorn exit cleanly on SIGINT/SIGTERM (timeouts, kill fallback documented). **Done** (best-effort interrupt → terminate → kill).
- **Health:** minimal `/api/health`-style hook or documented pattern (official router helper optional). **Done** (`/healthz` on the FastAPI app; available at `/<api_prefix>/healthz`).
- **Proxy edge cases:** large uploads, streaming responses, cookie/path edge cases behind `root_path` / subpaths (see Phase 4).
- **CI integration tests:** smoke test `fluxlit run` with a tiny app (optional; may be slow).

### Success criteria

- A new user runs `fluxlit new` + `fluxlit dev` without hand-tuning ports.
- API docs reachable at `/api/docs` when using default layout.

---

## Phase 2 — Developer experience

### Goals

- Less boilerplate, faster iteration, clearer errors when something is misconfigured.

### Planned features

| Feature | Notes | Status |
|--------|-------|--------|
| **Config file** | `fluxlit.toml` (top-level keys) / `[tool.fluxlit]` in `pyproject.toml`; `fluxlit.toml` wins if both exist. | **Done** |
| **Page discovery** | Opt-in `FluxLit.discover_pages("pages", package="pkg")` + `register(app)` per module. | **Done** |
| **Typed client** | `ApiClient.get_model` / `post_model` (Pydantic). OpenAPI codegen deferred. | **Done** (sync helpers) |
| **Hot reload** | Documented gateway-only reload; stderr warning; `--reload-scope=gateway`. | **Done** |
| **Logging** | Request id `ContextVar`, gateway DEBUG line, optional `enable_request_logging` on FastAPI. | **Done** |
| **`fluxlit doctor`** | Import, bind, deps, `FLUXLIT_INTERNAL_API_BASE`, Streamlit version WARN; `--warnings-only`. | **Done** |
| **`fluxlit build`** | Starter `Dockerfile` + `.dockerignore` (wheel/lockfile export still future). | **Done** (Docker template) |

### Success criteria

- `fluxlit doctor` catches common “it won’t start” issues before runtime. **Met** (import, bind, env shape).
- Reload path documented; no silent partial updates. **Met** (warning + docs).

---

## Phase 2 follow-on — Streamlit survives browser refresh (no cookies)

### Goals

- After a **full browser reload** (F5 / reopen tab to the same app URL), restore meaningful **application state** without relying on **HTTP cookies** (`Set-Cookie` / browser cookie jar).

### Why this is non-trivial

- Streamlit ties **`st.session_state`** to a **server session** tied to the live WebSocket/script run. A hard refresh often starts a **new** session, so in-memory state appears “lost” unless something **outside** that default session rehydrates it.

### Constraint

- **No cookies** for session binding or continuity. (Other storage mechanisms such as `localStorage` are intentionally **out of scope for v1** of this item to keep the contract simple: **URL + server store only**.)

### Recommended design: URL-bound opaque key + server-side store

| Piece | Detail |
|--------|--------|
| **Client-visible binding** | Stable **query parameter** on the public URL (e.g. `?fluxlit_sid=<opaque_token>`), readable via Streamlit **`st.query_params`**. Optional: configurable parameter name via `FluxlitSettings` / app helper. |
| **Token** | Cryptographically random (e.g. **≥128 bits**), unguessable; treat as a **secret** (same class as a bearer link). |
| **Store** | **Server-side** map: `token → serialized state blob` (or structured dict). Implementations: **in-memory** (single-worker dev only), **Redis** / similar (production, multi-worker), behind a small **`SessionStore` protocol** so apps can inject a backend. |
| **Hydration flow** | First visit without a token: mint token, persist initial state (or empty), **set query params** so the URL includes the token (`st.query_params` / navigation preserves params). On every run: if param present, **load** from store into `st.session_state` (merge vs replace is an app policy; FluxLit can document a default). |
| **Multipage** | With **`st.navigation`**, every linked page must **preserve** the same query string (helper API or wrapper pattern in docs) so refresh on any page still resolves the same token. |
| **Gateway** | No cookie logic required; proxy already forwards path + query to Streamlit. Optional future: strip token from logs / metrics for privacy. |
| **Security / UX** | **HTTPS** in production; document **link leakage** (bookmarks, Referer, shared URLs). Offer **TTL** and optional **rotation** in the store API; never log raw tokens at INFO. |
| **What “state” means** | Not Streamlit widget object identity—**serializable app state** the product cares about (filters, wizard step, draft form dict). Apps opt in to what gets persisted. |

### Deliverables (proposed)

| Item | Notes |
|------|--------|
| **Architecture note** | Short section in [FLUXLIT_PLAN.md](FLUXLIT_PLAN.md) tying this to the sidecar model. |
| **User guide** | README pattern: minimal example (memory store + query param + hydrate on run). |
| **Optional API** | `fluxlit.streamlit_session` (name TBD): `SessionStore` protocol, in-memory implementation, Redis adapter later; helper to “ensure sid in URL + hydrate”. |
| **Tests** | Streamlit **AppTest**: two runs with identical `st.query_params` assert restored state; contract tests for store. |

### Success criteria

- Documented pattern works for **single-user** continuity on refresh with **no cookies**, on **one** supported Streamlit minor (pin in docs).
- Clear **security** guidance (secret URL, HTTPS, TTL).
- Multi-worker production path documented (**Redis** or equivalent), not just in-memory.

### Relation to other phases

- **Phase 3 (sessions):** may later **combine** URL sid with signed cookies or JWT for **identity**; this item is **continuity**, not authentication.
- **Phase 4:** observability must **redact** session query params in access logs where possible.

---

## Phase 3 — Auth and sessions

### Goals

- Production-safe patterns that work behind corporate reverse proxies and modern IdPs.

### Features

- **Proxy trust:** headers (e.g. `X-Remote-User`) with explicit allowlists and tests.
- **Sessions:** signed cookies, optional Redis/session store interface.
- **JWT:** validate bearer tokens; optional JWKS rotation.
- **OAuth2/OIDC:** provider plugins (Azure AD, Okta, Google, GitHub) behind a small abstraction.
- **RBAC:** dependency helpers for FastAPI; Streamlit-side checks via shared session/JWT claims.

### Enterprise

- Document forward-auth / SSO front door patterns; CAC / smart-card flows where identity arrives via headers.

### Success criteria

- Reference app: login → API + Streamlit both see the same identity claims.
- Security review checklist in docs (cookies, CSRF, `root_path`, secure headers).

---

## Phase 4 — Production runtime

### Goals

- Operate like a service: observable, portable, and proxy-aware.

### Features

- **Health and readiness** for Kubernetes.
- **Metrics:** Prometheus-friendly endpoints or OpenTelemetry hooks.
- **Structured logging + tracing** correlation across gateway and API.
- **Docker:** official image or `Dockerfile` template; non-root user; multi-stage build.
- **Kubernetes:** example Deployment + Service + Ingress annotations.
- **`root_path` / `X-Forwarded-*`:** first-class docs and tests for subpath deployment.

### Success criteria

- One-command container run with documented env vars.
- Load test or soak notes for websocket proxy under concurrent users (baseline).

---

## Phase 5 — Native ASGI exploration

### Goals

- Reduce moving parts if Streamlit’s embedding model allows it without breaking websocket semantics.

### Research

- Streamlit ASGI / embedding APIs (version-gated).
- Single-process vs hybrid: gateway-only vs embedded UI.
- WebSocket lifecycle parity with current sidecar proxy.

### Outcomes (one or more)

- Document “sidecar recommended” vs “experimental embedded” with benchmarks.
- Optional `fluxlit run --native` if a safe path exists.

---

## Phase 6 — Ecosystem

### Goals

- Extend FluxLit without forking core.

### Features

- Plugin hooks (auth providers, deployment adapters, logging).
- Template gallery (minimal admin, data app, API-heavy).
- Background jobs / queues (optional integration, not core).
- Realtime patterns (SSE/WebSocket from FastAPI) documented with Streamlit consumers.

---

## Testing strategy

### Required coverage (by area)

| Area | Today | Target |
|------|--------|--------|
| Gateway HTTP | Partial (routing) | Proxy integration with mock upstream |
| Gateway WebSocket | Manual | Automated stability / reconnect cases |
| Runtime orchestration | Manual | CI smoke or subprocess contract tests |
| Auth (Phase 3) | — | Unit + integration with fake IdP |
| `root_path` / forwards | — | Regression tests with TestClient + headers |
| Streamlit URL-bound session (Phase 2 follow-on) | — | AppTest: re-run with same query params + store contract |

### CI targets

- **Linux** (required), **macOS** (recommended), **Windows** (recommended; subprocess + path quirks).

---

## Success metrics

### Developer experience

- Time to first working `fluxlit dev` under five minutes following README.
- Predictable errors; no “which port is Streamlit?” confusion.

### Production

- Documented deployment paths (Docker, K8s, reverse proxy).
- Observable failures (health, logs, metrics).

### Community

- Examples repo or `examples/` in tree.
- Clear versioning policy and upgrade notes for Streamlit major bumps.

---

## Versioning note

Roadmap phases do not map 1:1 to semver. Expect **0.x** to move quickly; **1.0** implies stable CLI/config contracts and a documented support matrix (Python + Streamlit versions).

---

## Related documentation

- [README.md](README.md) — install, quick start, CLI, configuration, routing
- [FLUXLIT_PLAN.md](FLUXLIT_PLAN.md) — product vision, architecture, risks, deployment goals
