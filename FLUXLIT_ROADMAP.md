# FluxLit — Development Roadmap

This document tracks **FluxLit** (`fluxlit` on PyPI): a unified FastAPI + Streamlit runtime. Phases are ordered for risk reduction: prove the gateway, harden operations, then deepen product features.

---

## Current status (0.1.x)

**Done**

- **Foundation:** `src/` layout, `pyproject.toml`, Hatchling build, Ruff, Mypy (strict), Pytest.
- **Unified dev/prod entry:** `fluxlit dev` / `fluxlit run` with a single public port; Streamlit runs in a managed subprocess with an internal port.
- **Gateway:** `/api/*` → FastAPI (path prefix stripped for the inner app); HTTP + WebSocket proxy to Streamlit for all other paths.
- **App model:** `FluxLit` holds `FastAPI` on `.api`, `@app.page` registers Streamlit pages; `ApiClient` for server-side calls with `FLUXLIT_INTERNAL_API_BASE`.
- **Scaffold:** `fluxlit new <name>` minimal app.
- **Tests:** gateway routing / OpenAPI prefix, page registration, `load_fluxlit` validation.

**Gaps vs “production”**

- No CI workflow yet (Linux / macOS / Windows matrix).
- Reload is experimental (`fluxlit dev --reload`); Streamlit lifecycle on reload is not fully orchestrated.
- Auth, metrics, Docker/K8s artifacts, and `fluxlit doctor` / `fluxlit build` are not implemented.

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
| CI (install, test, lint)    | **Todo** |
| Contributor docs / changelog | Todo   |

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

- **Graceful shutdown:** ensure Streamlit and Uvicorn exit cleanly on SIGINT/SIGTERM (timeouts, kill fallback documented).
- **Health:** minimal `/api/health`-style hook or documented pattern (official router helper optional).
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

| Feature | Notes |
|--------|--------|
| **Config file** | e.g. `fluxlit.toml` / `[tool.fluxlit]` — default target, host/port, log level. |
| **Page discovery** | Optional convention: auto-register `pages/*.py` alongside explicit `@app.page`. |
| **Typed client** | Pydantic models or OpenAPI-generated client for `ApiClient` (sync first). |
| **Hot reload** | Stable story: reload API only vs full stack; document limits with Streamlit. |
| **Logging** | Structured logging context (request id, route) shared across gateway and app hooks. |
| **`fluxlit doctor`** | Check Python version, deps, ports, `FLUXLIT_*`, Streamlit version. |
| **`fluxlit build`** | Define scope: Docker context only vs wheel + lockfile export. |

### Success criteria

- `fluxlit doctor` catches the top three “it won’t start” issues before runtime.
- Reload path documented; no silent partial updates.

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
