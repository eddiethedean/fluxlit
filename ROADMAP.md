# FluxLit — Development Roadmap

This document tracks **FluxLit** (`fluxlit` on PyPI): a unified FastAPI + Streamlit runtime. Phases are ordered for risk reduction: prove the gateway, harden operations, then deepen product features.

---

## Current status (0.4.x)

**Done**

- **Foundation:** `src/` layout, `pyproject.toml`, Hatchling build, Ruff, Mypy (strict), Pytest.
- **Unified dev/prod entry:** `fluxlit dev` / `fluxlit run` with a single public port; Streamlit runs in a managed subprocess with an internal port.
- **Gateway:** configurable API prefix (default `/api`); path prefix stripped for the inner FastAPI app; HTTP + WebSocket proxy to Streamlit for all other paths.
- **App model:** `FluxLit` holds `FastAPI` on `.api`, `@app.page` registers Streamlit pages; `ApiClient` for server-side calls with `FLUXLIT_INTERNAL_API_BASE`.
- **Scaffold:** `fluxlit new <name>` minimal app.
- **Tests:** gateway routing / OpenAPI prefix, page registration, `load_fluxlit` validation, CLI tests, ApiClient tests, Streamlit AppTest, FluxLit-native test client.
- **Readiness:** `GET /api/readyz` probes the Streamlit upstream when `FLUXLIT_STREAMLIT_UPSTREAM` is set (Kubernetes-style readiness; hidden from OpenAPI).
- **Dev reload:** `--reload-scope=gateway` (default) vs `--reload-scope=full` (Uvicorn reload plus Streamlit restart via `watchfiles`); invalid scope fails before spawning Streamlit.
- **Observability (baseline):** optional structured gateway access logs (`enable_gateway_access_log`); log redaction helpers for sensitive headers; temp-file upstream state so reload workers and Streamlit restarts stay aligned.
- **Tests (deeper):** async readiness probe against threaded upstreams; gateway access-log behavior; upstream file/env precedence; reload-watcher callback; extended redaction and doctor/auth import edge cases.
- **Unified ASGI:** `FluxLit` as a normal ASGI entrypoint (`uvicorn app:app`); lifespan bridged to the inner FastAPI app; regression suite in `tests/test_asgi_unified.py` (lifespan + concurrent HTTP, streaming body, sidecar failure) — foundation for **Version 0.5** soak/chaos work.

**Gaps vs “production”**

- CI adds **`slow-tests`**, **`coverage`** (artifact), Docker **proxy-smoke**, and Playwright **e2e** (including subpath); continue with soak/load and broader scenarios over time.
- **Metrics** (Prometheus / OTel), hardened Docker/K8s beyond `fluxlit build` + `examples/docker_compose`, and broader proxy edge cases remain open; optional **`fluxlit[auth]`** covers JWT/OIDC/BFF patterns from **Version 0.3** onward.
- **Browser refresh continuity** for Streamlit (cookie-free, URL + server store) is specified under **Phase 2 follow-on** in this file but not implemented yet.
- Deeper **operational maturity** (SLOs, runbooks, chaos/load, supply-chain, multi-replica guidance) is tracked under **Version 0.5** below.

**Next: 0.5.x**

- **Version 0.5** (below) is the planned **production-hardening** release: reliability, security supply chain, deployment/runbooks, observability, testing depth, and versioning/support policy — alongside ongoing **Phase 2 follow-on** (Streamlit refresh continuity) and **Phase 4** items folded into that slice where they overlap.

---

## Version 0.5 — Production hardening & operations (planned)

**Theme:** Close the gap between “runs well in dev/CI” and **operated production**: measurable reliability, defensible security posture, observable failure modes, and documented scale paths — without requiring a 1.0 semver freeze.

### Reliability & operations

| Feature | Description |
|---------|-------------|
| **Structured logging + correlation** | JSON logs in container images; one **request / trace** correlation id from gateway → FastAPI → Streamlit logs; document required fields for common log stacks. |
| **SLOs & alerting** | Documented SLO examples (e.g. p99 on `GET /api/healthz`, error budget on `GET /api/readyz`); map to alert rules, not only process liveness. See [SLOs & alerting](docs/observability.md#slos--alerting) in `docs/observability.md`. |
| **Graceful shutdown** | Document and test **SIGTERM** under real orchestrators (e.g. Kubernetes `preStop`, `terminationGracePeriodSeconds`): in-flight HTTP/WebSocket drain, Streamlit teardown order, and upper-bound timeouts. |
| **Backpressure & timeouts** | Explicit timeouts on httpx / WebSocket paths to the Streamlit upstream; optional max request body size; limits on concurrent upstream connections so a wedged sidecar cannot exhaust the gateway. |

### Security & supply chain

| Feature | Description |
|---------|-------------|
| **Dependency & image hygiene** | **SBOM** generation; **`pip-audit`** (or equivalent) in CI; pinned base images; reproducible lockfiles in templates where applicable. |
| **Container hardening** | **Non-root** user in generated and reference Dockerfiles; **read-only root filesystem** where compatible; least-privilege defaults in `fluxlit build` output. |
| **Secrets lifecycle** | Guidance and checks: no secrets in logs; integration patterns for secret stores; **JWT / OIDC secret rotation** runbook. |
| **TLS & edge headers** | Production checklist: **HSTS**, **CSP** notes for Streamlit-typical layouts, strict **`forwarded_allow_ips`** when trusting proxies; validate against real TLS termination (same as production). |

**Implemented in `main` (0.5.x):** CI uploads a **CycloneDX JSON** SBOM (same `.[auth]` install as `pip-audit`); `fluxlit build`, `examples/docker_compose/Dockerfile`, and `docker/proxy-deployment/Dockerfile` use **digest-pinned** `python:3.12-slim` and **`USER appuser`**; the Compose example ships **`requirements.in` / `requirements.txt`** from **`pip-compile`**; operator docs live in **`docs/secrets.md`**, **`docs/production-tls.md`**, and **`SECURITY.md`** (SBOM download). **Read-only root** remains documented (Kubernetes + tmpfs / writable paths) rather than forced in every reference image.

### Deployment & scale

| Feature | Description |
|---------|-------------|
| **Horizontal scale** | First-class docs: **sticky sessions** vs replica count vs Streamlit session model; when to add an external session store (ties to **Phase 2 follow-on**). |
| **Multi-worker stance** | Keep “**not supported** for unified in-process Uvicorn workers” explicit; document **supported alternatives** (e.g. one process per replica, or split gateway / Streamlit topology if a platform demands it). |

**Implemented in `main` (deployment):** **`docs/deployment.md`** horizontal scale + multi-worker sections and K8s checklist; **`examples/kubernetes/`** reference manifests.

### Testing & quality

| Feature | Description |
|---------|-------------|
| **Contract tests** | OpenAPI snapshot or consumer-driven tests to catch API vs UI drift in CI. |
| **Soak & load** | Long-running `fluxlit run` / `uvicorn` with sustained traffic; baseline WebSocket concurrency under load. |
| **Chaos & failure injection** | Scripted scenarios: Streamlit killed, slow upstream, partial network partition — aligned with `tests/test_asgi_unified.py` failure modes. |
| **Upgrade matrix** | CI matrix: **minimum and latest** supported Python, Streamlit, FastAPI/Starlette (or documented subset) to catch breakage early. |

**Implemented in `main` (testing):** OpenAPI **contract** test + fixture; ASGI **serial burst** `healthz` test; **`scripts/soak_http.sh`**; **`.github/workflows/upgrade-smoke.yml`** (weekly / manual, latest Streamlit/FastAPI/Starlette + fast tests, `continue-on-error`); documented in **`docs/testing.md`**. Full per-push min/max dependency matrix remains optional cost tradeoff.

### Observability

| Feature | Description |
|---------|-------------|
| **RED / USE metrics** | Prometheus-friendly metrics from the gateway (requests, latency, errors, upstream status class); optional **USE** for resource saturation. |
| **Distributed tracing** | OpenTelemetry hooks with context propagation across the gateway → internal API hop (aligns with **Version 0.3** “correlation” row). |
| **Runbooks** | One short runbook per common incident: **503 on `readyz`**, blank Streamlit, WebSocket failures behind nginx/Traefik, auth misconfig — linked from **troubleshooting** docs. |

**Implemented in `main` (observability):** **`docs/runbooks.md`** + links from troubleshooting/deployment/index; optional gateway **Prometheus** RED metrics (`FLUXLIT_ENABLE_GATEWAY_PROMETHEUS_METRICS`, `fluxlit[metrics]`); observability docs for **traceparent** / OTel recipe and **correlation limits** (gateway vs Streamlit process).

### Product, versioning & support

| Feature | Description |
|---------|-------------|
| **Semver & changelog discipline** | Clear **0.x** cadence; **CHANGELOG** entries per release; short **upgrade X → Y** checklist for breaking CLI/config/runtime changes. |
| **Support matrix** | Published “supported combinations” (Python × Streamlit × FluxLit); optional **LTS** or extended-support branch policy if demand warrants. |

**Implemented in `main` (product):** **`docs/support-matrix.md`**; maintainer **release checklist** in **`CONTRIBUTING.md`**.

### Success criteria (0.5)

- Operators can answer **“is it healthy?”**, **“why did it fail?”**, and **“how do I roll safely?”** from docs + defaults without reading source.
- CI blocks regressions on **authored** security/supply-chain gates agreed for the repo (audit/SBOM as adopted).
- At least one **reference deployment** path (e.g. Kubernetes example) matches hardened Dockerfile and env contract — see **`examples/kubernetes/`** in the repo.

### Relation to other roadmap items

- **Phase 4 (Production runtime):** 0.5 **implements the prioritized subset** (metrics, tracing correlation, K8s example, soak notes); remaining Phase 4 bullets stay until done or folded into later 0.x.
- **Phase 2 follow-on (URL-bound session):** complementary for **multi-replica** continuity; 0.5 documents scale limits until an external store exists.
- **Version 0.3:** security headers, correlation, and doctor extensions **feed** 0.5 TLS/proxy/runbook work.

---

## Version 0.3 — Security, identity, and cross-layer trust (released on PyPI)

**Theme:** Make **industry-standard auth** easy to wire correctly, with **one mental model** for both FastAPI routes and Streamlit pages — and **no accidental token leaks** through the browser, logs, or the Streamlit subprocess.

### Design principles

| Principle | What it means for FluxLit |
|-----------|---------------------------|
| **Server-side secrets** | Long-lived credentials (client secrets, API keys, refresh tokens) never touch `st.session_state` or the browser; they stay in FastAPI deps, env, or a secrets backend. |
| **Short-lived, scoped tokens** | Streamlit code receives **access tokens** (or opaque session handles) with tight **TTL**, **audience**, and **scopes** — ideally minted or exchanged via FastAPI, not hand-rolled in widgets. |
| **Explicit forwarding** | `ApiClient` gains first-class hooks for **Authorization**, **correlation IDs**, and optional **mTLS** / custom headers — with docs on what must **not** be forwarded to Streamlit’s origin. |
| **Gateway-aware URLs** | OAuth redirects, JWKS URLs, and post-logout redirects respect **`root_path`** and `X-Forwarded-*` so deployments behind proxies don’t break silently. |
| **Pythonic, composable APIs** | FastAPI dependencies you can `Depends()` on; small builders for OIDC discovery and JWKS; Streamlit helpers that read the **same** typed claims object as your API. |

### FastAPI layer — standards-first building blocks

| Feature | Description |
|---------|-------------|
| **JWT validation** | `Depends()`-style helpers: verify **iss**, **aud**, **exp**, **nbf**, **jti**; support **HS256** (dev) and **RS256/ES256** via **JWKS** with caching and **`kid`** rotation. |
| **OIDC / OAuth2** | Optional integrations: **Authorization Code + PKCE** for user login; **client credentials** for service accounts; provider presets (generic OIDC, Auth0-style, Azure AD, Google, GitHub) behind a small **protocol interface** so new IdPs don’t fork core. |
| **Token exchange & BFF-style** | Pattern: browser never holds opaque IdP refresh tokens; **FastAPI** exchanges codes and issues **first-party access tokens** (or session cookies) scoped to your API **audience** — Streamlit only sees what the BFF allows. |
| **RBAC / ABAC helpers** | Reusable dependencies: `require_scopes(...)`, `require_roles(...)`, claim-based predicates; same checks callable from Streamlit-facing helpers for parity. |
| **API keys & mTLS** | Documented patterns for machine clients: header-based keys, optional client certificate hints for enterprise front doors. |
| **Security middleware** | Opt-in baseline: **HSTS**, **X-Content-Type-Options**, **frame-ancestors** / CSP notes for Streamlit-typical layouts; **CORS** presets that fail closed in production. |
| **CSRF** | If cookie-based sessions are introduced: **double-submit** or **SameSite=strict** defaults + FastAPI helpers; document Streamlit limitations and recommended BFF flows. |

### Streamlit layer — calling FastAPI safely

| Feature | Description |
|---------|-------------|
| **Authenticated `ApiClient`** | Constructors/factory that bind a **callable** or **ContextVar** for the current access token (or use **server-side session** IDs that FastAPI resolves — no raw refresh tokens in Streamlit). |
| **Claims in page functions** | Optional `st`-safe DTO: same **Pydantic model** (or TypedDict) as FastAPI route dependencies so UI logic doesn’t parse JWTs manually. |
| **Header & cookie policy** | Clear rules: which headers `ApiClient` sends on **internal** `FLUXLIT_INTERNAL_API_BASE` calls; how to avoid echoing **Authorization** into Streamlit debug or `st.write`. |
| **Token refresh without leaking** | Background refresh delegated to FastAPI (`/auth/refresh` or opaque cookie); Streamlit only requests a new short-lived token through that channel. |
| **User identity for widgets** | Helpers: “current user” display name / id from validated claims — never from unverified JWT payload strings in the browser. |

### Gateway & runtime — operational safety

| Feature | Description |
|---------|-------------|
| **Request correlation** | Propagate **X-Request-ID** (already present) into internal API calls and optional **OpenTelemetry** trace context later (align with Phase 4). |
| **Log redaction** | Central guidance + helpers to **redact** `Authorization`, cookies, and sensitive query params in access logs (pairs with Phase 2 follow-on URL tokens). |
| **Rate limiting hooks** | Optional integration points (e.g. Starlette middleware or external sidecar) documented for the single public port. |
| **`fluxlit doctor` extensions** | Checks: auth env vars present, **HTTPS** in production templates, clock skew warnings for JWT, `FLUXLIT_INTERNAL_API_BASE` still loopback-safe. |

### Documentation & examples

| Deliverable | Purpose |
|-------------|---------|
| **Security architecture page** | Diagram: browser → gateway → FastAPI vs Streamlit; where tokens live; threat model (XSS, CSRF, token replay). |
| **Reference recipes** | “OIDC login + Streamlit dashboard”, “Machine API key + internal ApiClient”, “Forward-auth headers from nginx”. |
| **Migration guide** | From no-auth apps to JWT — incremental steps without breaking `fluxlit run`. |

### Testing & quality bar

- Contract tests with **fake OIDC** (JWKS server fixture) and clock control for **exp** / **nbf**.
- Regression tests: `ApiClient` never logs tokens; internal base URL doesn’t strip auth incorrectly.
- **Optional** dependency group `auth` (e.g. `PyJWT` / `httpx` + JOSE stack) so minimal installs stay lean.

### Relation to other roadmap items

- **Phase 2 follow-on (URL-bound session):** complementary — use **opaque sid** for Streamlit continuity; bind **JWT subject** to sid server-side rather than putting JWT in the query string.
- **Phase 4 (production):** metrics and tracing must **label** routes without leaking PII; security headers middleware aligns with hardened Docker/K8s.

### Success criteria (0.3)

- A **single reference app** demonstrates login → JWT (or first-party token) → Streamlit page calling FastAPI with **the same identity** and **no duplicate auth logic**.
- Docs include a **security checklist** (cookies, CSRF, `root_path`, token storage, HTTPS).
- Optional **`fluxlit[auth]`** (name TBD) installs audited auth dependencies with pinned lower bounds.

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
| **Hot reload** | `--reload-scope=gateway` (default) vs `full` (restart Streamlit on changes via `watchfiles`); stderr documents behavior; invalid scope rejected at CLI and runtime. | **Done** |
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
| **Architecture note** | Short section in [PLAN.md](PLAN.md) tying this to the sidecar model. **Done** (browser refresh / session continuity). |
| **User guide** | Minimal example (memory store + query param + hydrate on run). **Done:** `docs/url-session.md`. |
| **Optional API** | **`fluxlit.url_session`:** `SessionStore`, `InMemorySessionStore`, `ensure_url_session` / `hydrate_url_session` / `persist_url_session`; Redis remains app-specific. |
| **Tests** | **AppTest** second run after clearing user session keys; unit tests for store + helpers. **Done** (`tests/test_url_session*.py`). |
| **Observability** | Gateway access log **`query`** redacts `fluxlit_sid` and `FLUXLIT_URL_SESSION_QUERY_PARAM`. **Done.** |

### Success criteria

- Documented pattern works for **single-user** continuity on refresh with **no cookies**, on **one** supported Streamlit minor (pin in docs).
- Clear **security** guidance (secret URL, HTTPS, TTL).
- Multi-worker production path documented (**Redis** or equivalent), not just in-memory.

### Relation to other phases

- **Phase 3 (sessions):** may later **combine** URL sid with signed cookies or JWT for **identity**; this item is **continuity**, not authentication.
- **Phase 4:** observability must **redact** session query params in access logs where possible. **Done** for gateway structured `query` (see `fluxlit.logging.redact.redact_query_string`).

---

## Phase 3 — Auth and sessions

### Goals

- Production-safe patterns that work behind corporate reverse proxies and modern IdPs.
- **Version 0.3** delivers the first concrete slice of this phase; later 0.x releases deepen observability (Phase 4) and ecosystem plugins (Phase 6).

### Features (summary — detail under **Version 0.3** above)

- **Proxy trust:** headers (e.g. `X-Remote-User`) with explicit allowlists and tests.
- **Sessions:** signed cookies or opaque server sessions; optional Redis/session store interface; **no long-lived secrets in Streamlit state**.
- **JWT:** validate bearer tokens; **JWKS** with **kid** rotation and caching; **aud** / **iss** enforcement.
- **OAuth2/OIDC:** Authorization Code + **PKCE**, token exchange, provider presets behind a small abstraction.
- **Streamlit ↔ FastAPI:** authenticated **`ApiClient`**, shared claim models, documented header/cookie policy.
- **RBAC:** dependency helpers for FastAPI; Streamlit-side checks via the same claims DTOs.

### Enterprise

- Document forward-auth / SSO front door patterns; CAC / smart-card flows where identity arrives via headers.
- **mTLS** and enterprise IdP notes where identity is asserted by the edge, not the app.

### Success criteria

- Reference app: login → API + Streamlit both see the **same validated identity** without duplicating JWT logic.
- Security review checklist in docs (cookies, CSRF, `root_path`, secure headers, token storage).

---

## Phase 4 — Production runtime

### Goals

- Operate like a service: observable, portable, and proxy-aware.

**Tracking:** concrete delivery and acceptance criteria for the next wave of Phase 4 work are folded into **Version 0.5** above (metrics, tracing, hardened containers, K8s example, soak/load, runbooks).

### Features

- **Health and readiness** for Kubernetes — **partial:** liveness (`/api/healthz`) and readiness (`/api/readyz` vs Streamlit) shipped; multi-probe charts and operator runbooks still TBD (**0.5**).
- **Metrics:** Prometheus-friendly endpoints or OpenTelemetry hooks (**0.5**).
- **Structured logging + tracing** correlation across gateway and API — **partial:** optional per-request gateway INFO logs with structured `extra`; full trace propagation still TBD (**0.5**).
- **Docker:** official image or `Dockerfile` template; non-root user; multi-stage build (**0.5** hardening on template output).
- **Kubernetes:** example Deployment + Service + Ingress annotations (**0.5**).
- **`root_path` / `X-Forwarded-*`:** first-class docs and tests for subpath deployment (ongoing; **0.5** runbooks for common proxy failures).

### Success criteria

- One-command container run with documented env vars.
- Load test or soak notes for websocket proxy under concurrent users (baseline) — **0.5** soak/chaos items.

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
| Unified ASGI (v0.5 prep) | `tests/test_asgi_unified.py`: lifespan + concurrent HTTP, httpx + `TestClient`, streaming body, sidecar failure | Soak/chaos suites as **0.5** lands |
| Gateway HTTP | TestClient + threaded upstream (gzip, redirects); forwarded-header assertions; access-log on/off; `readyz` with fake upstream | More edge cases (timeouts, trailers) |
| Gateway WebSocket | Echo/proxy + **`slow`** multi-session stress (`tests/test_gateway_ws_echo.py`) | Heavier reconnect soak remains optional / manual |
| Runtime orchestration | Subprocess `run_unified` + `/api/healthz` (`slow`); upstream state read/write; invalid `reload_scope` before Streamlit spawn; reload-watcher unit test | Optional deeper lifecycle tests |
| Health / readiness | Async probe tests (200/500/refused); `readyz` via gateway + FluxLit | Broader failure modes and timeouts |
| Auth (Phase 3 / v0.3) | Fake JWKS server, JWT/OIDC edge cases; `ApiClient` must not log bearer secrets | Broader IdP matrices |
| `root_path` / forwards | Forwarded headers + Playwright subpath E2E | Regression matrix for more proxy shapes |
| Streamlit URL-bound session (Phase 2 follow-on) | `tests/test_url_session.py`, `tests/test_url_session_apptest.py` | AppTest second run + store unit tests |

### CI targets

- **Linux** (required), **macOS** (recommended), **Windows** (recommended; subprocess + path quirks).
- **Coverage** job (Linux / Python 3.12) uploads `coverage.xml`; **`slow-tests`** runs marked subprocess tests; **proxy-smoke** and **e2e** jobs cover Docker nginx and browser stacks.

---

## Success metrics

### Developer experience

- Time to first working `fluxlit dev` under five minutes following README.
- Predictable errors; no “which port is Streamlit?” confusion.

### Production

- Documented deployment paths (Docker, K8s, reverse proxy).
- Observable failures (health, logs, metrics).
- **Version 0.5:** SLO-oriented readiness, runbooks, metrics/tracing, supply-chain and container hardening, soak/chaos and upgrade-matrix CI — see **Version 0.5** section.

### Community

- Examples repo or `examples/` in tree.
- Clear versioning policy and upgrade notes for Streamlit major bumps.

---

## Versioning note

Roadmap phases do not map 1:1 to semver. Expect **0.x** to move quickly; **1.0** implies stable CLI/config contracts and a documented support matrix (Python + Streamlit versions).

---

## Related documentation

- [README.md](README.md) — install, quick start, CLI, configuration, routing
- [PLAN.md](PLAN.md) — product vision, architecture, risks, deployment goals
