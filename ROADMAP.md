# FluxLit — Development Roadmap

This document tracks **FluxLit** (`fluxlit` on PyPI): a unified FastAPI + Streamlit runtime. Phases are ordered for risk reduction: prove the gateway, harden operations, then deepen product features.

---

## Path to 1.0 (phased plan)

<a id="path-to-1-0"></a>

**1.0** means a deliberate **stability promise** for teams shipping to production: documented **CLI** commands and flags, **`fluxlit.toml` / `[tool.fluxlit]`** keys called out as stable, the **`FLUXLIT_*`** surface described in configuration docs, and **public Python APIs** (package exports and documented helpers such as `FluxLit`, `ApiClient`, `FluxLitTestClient`, page typing utilities, and optional `fluxlit[auth]` entry points). Breaking changes after 1.0 follow **semver** with **deprecation windows** where practical; experimental features stay explicitly labeled until promoted.

The sections below (**Current status**, **Version 0.x**, **Phase 0–6**) keep **historical and thematic** detail. This spine is the **forward-looking** sequence to GA.

| Phase | Target line | Primary goal |
|-------|-------------|--------------|
| **1** | **0.10.1 → 0.11.x** | Close operational and documentation gaps without growing unstable API surface. |
| **2** | **0.12.x** | Evidence-backed production contracts (multi-replica, load/chaos, stability charter for metrics/manifest/settings). |
| **3** | **1.0.0rc*** | Release candidate: freeze intentional breaking changes; migration guides; RC-blocker triage only. |
| **4** | **1.0.0** | General availability: semver promise + published support matrix as the compatibility contract. |

### Phase 1 — 0.10.1 → 0.11.x: Hardening and gap closure

**Goal:** Burn down known rough edges on **documented golden paths** (local `fluxlit dev` / `run`, reference Compose, Kubernetes manifests, proxy smokes: nginx, Traefik, Caddy, subpaths).

**Workstreams**

- **Operational:** broaden proxy matrices and cookbook recipes as real deployments surface edge cases; extend `fluxlit doctor` / verbose JSON where it prevents misconfigured production (headers, `root_path`, WebSocket expectations, timeouts).
- **Quality bar:** keep **100%** line coverage on `src/fluxlit` and existing CI gates (Ruff, Mypy, `ty`, docs `-W`, audit/SBOM) green on the published [support matrix](docs/support-matrix.md).
- **Product:** patch-level fixes for gateway → Streamlit proxy, async `Depends`, optional header forwarding, and Streamlit page typing — without new **stable** contracts unless they fill a documented hole.

**Exit criteria (enter Phase 2)**

- No open **P0/P1** defects on golden paths; remaining issues are **documented limitations** with workarounds, or scheduled for Phase 2 with an issue link.
- **Gaps vs “production”** (in **Current status** below) reviewed: each item is either **done**, **scoped to Phase 2**, or **explicitly out of scope for 1.0** (called out in this file).

### Phase 2 — 0.12.x: Evidence, multi-replica clarity, and stability charter

**Goal:** Replace “we believe it scales” with **repeatable evidence** and a clear **what is stable for 1.0** story.

**Workstreams**

- **Evidence:** publish or extend scripted **load / soak / chaos** scenarios with expected signals (metrics, logs, `readyz`); align outcomes with [runbooks](docs/runbooks.md).
- **Scale:** first-class docs for **multi-replica** Streamlit + gateway: sticky sessions, external `SessionStore` (e.g. Redis), rollout/drain — building on existing examples and URL-session guides.
- **Stability charter:** classify **Prometheus metric names/labels**, **page manifest** fields (`manifest_version` 1), log field names, and experimental settings (`experimental_yield_pages`, etc.) into **stable for 1.0** vs **experimental** in docs; adjust code comments/README if needed so CI and operators share one vocabulary.
- **DX:** clearer startup and CLI errors for invalid combinations (unsafe `forwarded_allow_ips`, `public_base_url` / `root_path` mismatch). **0.11.0** ships lifespan fail-fast for unified Uvicorn ``workers`` > 1 (see [docs/deployment.md](docs/deployment.md)); remaining DX items are follow-ups.

**Exit criteria (enter Phase 3)**

- Runbooks and observability docs describe what FluxLit emits, what it **does not** emit, and how to correlate gateway, API, and Streamlit-side logs under load.
- Support matrix includes a concise **1.0 compatibility commitment** (Python, Streamlit, core deps) and **deprecation policy** for the 1.x line.
- No **hidden** public API that downstreams rely on without docs — either document and freeze, or mark internal.

### Phase 3 — 1.0.0rc*: Release candidate and migration freeze

**Goal:** Validate real upgrades and freeze breaking changes except agreed RC fixes.

**Workstreams**

- Ship **`1.0.0rcN`** to PyPI; gather feedback on upgrade paths from **last 0.12.x** (or last pre-1.0 minor).
- **CHANGELOG** and **migration guide**: list behavior changes, removed shims, and config renames since the last stable 0.x.
- **API audit:** resolve deprecations; remove or shim with a clear removal version in 1.x.
- **Security / supply chain:** maintain or improve SBOM, `pip-audit`, and container baseline from last 0.x.

**Exit criteria (ship 1.0.0)**

- No **RC-blocker** issues on stable CLI, config, and documented public APIs.
- Docs site **stable** branch describes 1.0 as current; quickstart and deployment guides tested against RC artifacts.

### Phase 4 — 1.0.0: General availability

**Deliverables**

- **`fluxlit==1.0.0`** on PyPI; git tag `v1.0.0`.
- **Semver commitment** for the scoped stable surface; **Streamlit / FastAPI major** upgrades handled via FluxLit semver minor/patch with matrix updates (exact policy text lives in support matrix + changelog).
- **Post-1.0 roadmap** (does **not** block 1.0): **Phase 5** native ASGI / embedding research, **Phase 6** plugin ecosystem, deeper OpenTelemetry, broader IdP/proxy matrices, optional per-push min/max dependency CI — continue as 1.1+ work.

### 1.0 readiness checklist (summary)

| Area | Must be true at 1.0 |
|------|---------------------|
| **Runtime** | Sidecar gateway model documented; HTTP + WebSocket proxy behavior and limits documented. |
| **Operations** | `healthz` / `readyz`, graceful shutdown, gateway timeouts and body limits, structured logging story. |
| **Configuration** | Documented precedence (CLI → env → file → defaults); `fluxlit config` matches runtime. |
| **Security** | TLS/proxy trust, secrets, and auth (`fluxlit[auth]`) documented; optional metrics extra stable where promised. |
| **Developer** | `FluxLitTestClient`, AppTest helpers, page manifest + validate CLI, optional typed pages stable per charter. |
| **Release** | Support matrix, upgrade guide, and semver/deprecation policy published. |

---

## Current status (0.12.x)

**Shipped (0.12.0) — Phase 2 baseline**

- **Stability charter:** Prometheus metric / label / bucket policy, manifest ``manifest_version`` 1 fields, structured log contracts, experimental settings, and draft **1.0 compatibility** text in {doc}`support-matrix` / {doc}`observability`.
- **Multi-replica:** deployment checklist, runbook for **new session after refresh**, URL-session cross-links, optional **Kubernetes** PDB + Service session-affinity examples.
- **Evidence:** ``scripts/soak_readyz.sh``, chaos/soak script expectations in headers, runbooks **scripted load** table, manual workflow [`.github/workflows/soak-fluxlit-dispatch.yml`](.github/workflows/soak-fluxlit-dispatch.yml), {doc}`testing` recipe.
- **DX:** ``fluxlit doctor --strict`` fails on broad ``forwarded_allow_ips`` with ``trust_proxy`` and on ``public_base_url`` path vs mount mismatch (``fluxlit config --strict`` still fails on any warning).

**Previously (0.11.0)**

- **Unified multi-worker guard**, **Traefik** proxy smoke, **cookbook** / **doctor** diagnostics (rejected forward-header names, ``trust_proxy`` + unlimited body warn), **Packaging** sdist venv excludes, **env_parse** consolidation, **Release & CI** notes and PyPI immutability lesson — see **0.11.0** on PyPI and {doc}`changelog`.

**Done (0.10.0)**

- **Gateway header bridge:** optional ``FLUXLIT_GATEWAY_FORWARD_CLIENT_HEADERS_TO_STREAMLIT`` / :class:`~fluxlit.config.FluxlitSettings.gateway_forward_client_headers_to_streamlit` allowlists browser header names onto the gateway → Streamlit **HTTP** hop (rejects credentials / hop-by-hop); :class:`~fluxlit.pages.di.Header` also reads ``st.context.headers`` after :func:`~fluxlit.pages.di.set_page_header_context`.
- **Async Depends:** when ``FLUXLIT_ASYNC_PAGE_DEPENDS=1`` and an asyncio loop is already running, dependencies resolve on a **short-lived side thread** instead of raising ``TypeError``.
- **Operational polish:** Caddy strip-prefix added to the Docker proxy smoke matrix; ``fluxlit doctor`` adds readiness/WebSocket/timeout/async/forward-header signals; ``fluxlit doctor --verbose`` includes a ``gateway_proxy`` block; new {doc}`cookbook` and deployment proxy compatibility table.

**Previously (0.9.0+)**

- **Typed Streamlit pages:** :class:`~fluxlit.pages.records.PageRecord` registry; :meth:`~fluxlit.app.FluxLit.page` with ``icon``, ``tags``, ``page_meta``; :class:`~fluxlit.pages.di.Depends`, :class:`~fluxlit.pages.di.Header`, :class:`~fluxlit.pages.di.Cookie`; optional :class:`~fluxlit.url_session.SessionStore` injection; strict registration via :class:`~fluxlit.config.FluxlitSettings.strict_page_signatures`.
- **Navigation:** :meth:`~fluxlit.app.FluxLit.navigation` with :class:`~fluxlit.pages.navigation.NavigationModel` ordering; ``PageMeta.children`` merges display overrides and sidebar order in the Streamlit entrypoint; ``?page=`` deep links align with that order (see :doc:`deep-links`).
- **Manifest / CLI:** :meth:`~fluxlit.app.FluxLit.build_page_manifest` (``manifest_version`` **1**, **stable**); ``fluxlit pages manifest`` and ``fluxlit pages validate`` for CI.
- **Doctor / config:** ``fluxlit doctor --verbose`` snapshots; ``--check-pages`` runs validate-style checks; settings expose ``experimental_yield_pages`` and ``async_page_depends`` for env parity.
- **Async Depends (0.9 baseline):** ``FLUXLIT_ASYNC_PAGE_DEPENDS=1`` resolved async dependency callables with ``anyio.run`` when no asyncio loop is running (see :doc:`streamlit-pages-typing`).
- **0.8.x foundation** (gateway, URL session, testing client, observability, docs) remains as documented in prior roadmap sections.
- **Pins:** Optional env-driven features and supported Python / Streamlit ranges are summarized in [docs/support-matrix.md](docs/support-matrix.md).

**Next: 0.13.x / Phase 2 follow-through** — evidence **baselines** (published numbers, optional CI expansion), OpenTelemetry depth, stability-charter **enforcement** in code where drift-prone, and remaining DX hard-errors. Phase 3 (**1.0.0rc***) gates remain in **[Path to 1.0](#path-to-1-0)**.

### Phase 2 — delivery checklist (track as issues/milestones)

Use your issue tracker or release milestones to burn these down; this list mirrors Phase 2 in **[Path to 1.0](#path-to-1-0)** above.

- [x] **Evidence:** scripted load/soak/chaos runs with expected signals (metrics, logs, `readyz`) aligned with [docs/runbooks.md](docs/runbooks.md) — **0.12.0** ships ``soak_readyz``, script/runbook alignment, and optional **workflow_dispatch** soak; broader baselines / scheduled FluxLit soak remain follow-on.
- [x] **Multi-replica:** first-class docs for horizontal scale (sticky sessions, external `SessionStore`, rollout/drain) building on URL-session and examples — **0.12.0** checklist + K8s examples + runbook.
- [x] **Stability charter:** classify Prometheus metric names/labels, page manifest fields (`manifest_version` 1), log field names, and experimental settings as stable vs experimental in docs (and code comments where it prevents drift) — **0.12.0** tables in {doc}`support-matrix` / {doc}`observability`.
- [x] **DX / misconfiguration:** clearer diagnostics for ``forwarded_allow_ips`` / ``public_base_url`` vs mount — **0.12.0** adds ``fluxlit doctor --strict`` (plus **0.11.0** lifespan fail-fast for Uvicorn ``workers`` > 1); further hard-errors and richer hints remain for **0.13.x**.

### Suggested PR slices (implementation tracking)

Split Phase 2 work so each change stays reviewable and bisectable:

- **Evidence / load:** **0.12.0:** ``soak_readyz``, runbook/testing alignment, ``soak-fluxlit-dispatch`` workflow — extend with published SLO numbers / optional scheduled FluxLit soak.
- **Multi-replica:** **0.12.0** checklist + examples — deepen external ``SessionStore`` recipes and engine-specific ingress notes as needed.
- **Stability charter:** **0.12.0** docs tables — mirror into code comments / settings docstrings where operators grep.
- **DX / misconfiguration:** **0.12.0** ``doctor --strict`` for proxy allowlist + public URL path; **0.11.0** lifespan guard for multi-worker — follow-ups: hard errors for additional combos, richer ``fluxlit config`` overlap.
- **Dependency hygiene:** when bumping **httpx**, re-audit private imports in [`src/fluxlit/client.py`](src/fluxlit/client.py) (`httpx._types`, `httpx._client`) against the release’s public typing surface (noting intentional use in [docs/support-matrix.md](docs/support-matrix.md)).

**Gaps vs “production”**

- CI includes **`slow-tests`**, **`docs`** (coverage XML artifact, generated-doc snapshot check, Sphinx **`-W`**), Docker **proxy-smoke**, Playwright **e2e** (including subpath), audit/SBOM, upgrade smoke, and a scheduled soak-script check; continue with broader load/chaos scenarios over time. **Release** workflow parity with the **`docs`** job on tag pushes is exercised on each release tag; align tags with PyPI before upload or bump **patch** when artifacts must change.
- **Prometheus metrics**, hardened Docker/K8s references, runbooks, and `fluxlit[auth]` are available; deeper OpenTelemetry integration, broader proxy matrices, and production-scale validation remain ongoing.
- **Browser refresh continuity** ships for cookie-free URL + server-store patterns, including test-mode defaults for AppTest; production multi-replica continuity still requires an app-provided external store such as Redis.
- Deeper **operational maturity** remains ongoing: load baselines, chaos scenarios, ecosystem deployment recipes — **1.0 readiness** is now spelled out in **[Path to 1.0](#path-to-1-0)** above.

**Triage: 0.12.0 vs deferred (0.13.x / Phase 2 follow-on)**

| Topic | 0.12.0 | Deferred |
|-------|--------|----------|
| Stability charter (docs) | **Done** (support-matrix + observability + draft 1.0 text) | Code-comment mirroring, enforcement tests |
| Multi-replica ops narrative | **Done** (checklist, runbook, K8s examples, url-session links) | Deeper engine-specific ingress / external store cookbooks |
| Evidence scripts + runbook alignment | **Done** (``soak_readyz``, headers, runbooks table, manual workflow) | Published numeric baselines, optional scheduled FluxLit soak in CI |
| ``fluxlit doctor --strict`` (proxy / public URL path) | **Done** | Additional FAIL rows, startup-time hard errors |
| Broader load/chaos **evidence** | Partially | **0.13.x** — SLO numbers, longer soak jobs |
| OpenTelemetry depth | Hooks + docs recipes | **0.13.x** — fuller propagation story |
| Per-push min/max dependency matrix | — | Optional / **post-1.0** cost tradeoff (see support matrix) |
| Git tag vs PyPI byte identity | Documented practice | Bump **patch** when artifacts must change |

---

## Version 0.5 — Production hardening & operations (released)

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
- **Phase 2 follow-on (URL-bound session):** shipped for in-process and app-provided stores; remaining work is production recipes for external stores and multi-replica continuity.
- **Version 0.3:** security headers, correlation, and doctor extensions **feed** 0.5 TLS/proxy/runbook work.

---

## Version 0.6 — Production proof points & ecosystem hardening (released)

**Theme:** Turn the 0.5 production-hardening foundation into repeatable evidence: load/chaos results, richer tracing hooks, multi-replica state recipes, and compatibility signals that help teams adopt FluxLit with fewer bespoke decisions.

### Reliability evidence

| Feature | Description |
|---------|-------------|
| **Load baselines** | Publish repeatable HTTP and WebSocket load runs for the unified gateway, including expected machine shape, user-count assumptions, limits, and failure modes. |
| **Chaos scenarios** | Script and document Streamlit kill/restart, slow upstream, oversized body, dropped WebSocket, and gateway shutdown scenarios so operators know what degradation looks like. |
| **Proxy matrix** | Expand nginx / Traefik / full-path / strip-prefix coverage into a documented compatibility matrix with known-good config snippets and smoke commands. |
| **Readiness diagnostics** | Extend `fluxlit doctor` and runbooks with targeted checks for upstream reachability, root-path mismatches, proxy header trust, WebSocket upgrade paths, and stale sidecar state files. |
| **Release smoke app** | Maintain a small canonical smoke app used by local scripts, Docker proxy smokes, and release verification so docs, examples, and CI exercise the same public contract. |

### State and scale

| Feature | Description |
|---------|-------------|
| **External URL-session store recipes** | Provide Redis or database-backed `SessionStore` examples for `fluxlit.url_session`, with TTL, rotation, redaction, and multi-replica notes. |
| **Replica playbooks** | Document sticky-session tradeoffs, external state requirements, and rollout/drain guidance for Kubernetes and similar orchestrators. |
| **Example hardening** | Add production-minded variants of the reference apps that show secrets, auth, session continuity, and deployment wiring together without turning examples into frameworks. |
| **Platform recipes** | Add focused guides for common hosts such as Render/Fly.io/Railway-style containers, ECS/Fargate, and Posit Connect/Workbench where root paths and process models often differ. |
| **Configuration validation** | Add clearer startup or `doctor` diagnostics for invalid combinations such as multi-worker unified mode, public base URL / root path mismatches, and unsafe proxy trust defaults. |

### Developer and migration experience

| Feature | Description |
|---------|-------------|
| **Upgrade guide** | Publish a concise `0.5 -> 0.6` guide that separates behavior changes, deprecations, new defaults, and optional hardening steps. |
| **Scaffold profiles** | Consider `fluxlit new` profiles for minimal, auth-ready, and deployment-ready examples so users can start from a realistic shape without copying large demos. |
| **Extension points** | Document stable extension hooks for auth, session stores, logging, tracing, and custom deployment wrappers so downstream apps do not depend on private modules. |
| **Failure messages** | Improve user-facing errors for import-target failures, Streamlit startup failures, invalid sidecar args, and proxy body-limit rejections with direct remediation hints. |

### Observability and compatibility

| Feature | Description |
|---------|-------------|
| **OpenTelemetry hooks** | Add small, optional tracing integration points for gateway dispatch, upstream proxy calls, and internal API calls without requiring OTel as a core dependency. |
| **Dependency matrix** | Promote latest-dependency smoke signals into a clearer support policy for Python, FastAPI/Starlette, Streamlit, Uvicorn, and httpx ranges. |
| **Release hygiene** | Decide which 0.x deprecations or compatibility shims should be removed, documented, or carried forward before 1.0 planning. |
| **Log schema reference** | Document stable field names for gateway access logs, JSON formatter extras, request IDs, redacted query strings, and error classes so teams can build dashboards safely. |
| **Metrics contract** | Define which Prometheus metric names and labels are stable enough for alerts, and which remain experimental to avoid accidental cardinality or compatibility promises. |

**Implemented in `main` (0.6 / 0.7 / 0.8):** canonical smoke app and richer local smoke/load scripts; Docker proxy smoke matrix; external URL-session store examples; platform docs; optional tracing hooks and OpenTelemetry recipe; stable gateway log and Prometheus metric contracts; scaffold profiles; expanded `fluxlit doctor --json`; public `streamlit_main_path()` testing helper; official Pytest/AppTest recipe; URL-session test-mode defaults; monorepo import diagnostics; public-base-url precedence checks; multipage AppTest example; `fluxlit config` for effective settings and warnings; and an expanded support matrix for production pinning.

### Success criteria (0.6)

- Operators can reproduce at least one load test, one chaos test, and one proxy smoke path locally or in CI-like automation.
- Multi-replica deployments have a documented session-continuity path that does not rely only on process memory.
- Tracing and metrics guidance explains what FluxLit emits, what it intentionally does not emit, and how to correlate gateway, API, and Streamlit-side evidence.
- New projects can choose a scaffold or example path that matches their deployment intent without reading the runtime source.
- Release notes, upgrade guidance, and support-matrix changes make it clear what is stable, experimental, or intentionally deferred to 1.0.

---

## Version 0.7 — Testing and diagnostics polish (released)

**Theme:** Make the 0.6 feature set easier to test, diagnose, and adopt in real app
repositories, especially monorepos and Streamlit AppTest suites.

### Shipped

- **Testing API:** public `streamlit_main_path()` and `FluxLitTestClient.streamlit()` integration with `FLUXLIT_TESTS=1`.
- **Official testing recipe:** app-developer Pytest docs for `FluxLitTestClient`, Streamlit `AppTest`, API-prefix expectations, `ApiClient`, `st.data_editor`, stable `key=`, and browser E2E boundaries.
- **URL-session test mode:** helpers no-op under `FLUXLIT_TESTS=1` unless `FLUXLIT_FORCE_URL_SESSION_IN_TESTS=1`; explicit `FLUXLIT_DISABLE_URL_SESSION=1` remains available.
- **Import hygiene:** conservative top-level target candidate diagnostics for `app` / `main` shadowing, plus monorepo troubleshooting guidance.
- **Doctor/config DX:** additive doctor rows for loaded module file, `sys.path`, effective API/config state, URL-session state, public-base-url precedence, and missing `auth` / `metrics` extras.
- **Multipage AppTest:** minimal example under `examples/multipage_apptest/` and docs for supported smoke-test patterns plus current navigation-heavy limitations.

### Success criteria (0.7)

- App authors can copy a Pytest recipe for API tests and thin Streamlit smoke tests without inspecting FluxLit internals.
- Doctor output explains common import, proxy, URL-session, extras, and public-base-url mistakes before deployment.
- URL-session continuity remains production-friendly while AppTest defaults avoid unstable browser-query behavior.

---

## Version 0.8 — Configuration visibility and docs (released)

**Theme:** Make effective configuration inspectable before deploy, and document production dependency pinning more explicitly.

### Shipped

- **CLI:** `fluxlit config` prints resolved binding, redacted settings, derived internal API base, structured warnings with documentation links, and optional `--json` / `--strict`.
- **Docs / policy:** support matrix expanded for `uv` / `pip-tools` / constraints, Streamlit extra guidance, testing compatibility notes, and README cross-links.

### Success criteria (0.8)

- Operators can dump effective FluxLit configuration without starting the full stack.
- Production pinning guidance names core packages and upgrade expectations alongside the CI matrix.

---

## Version 0.9 — Typed Streamlit pages & developer contracts (released)

**Status:** Shipped on PyPI as **0.9.0**. Follow-on work (async `Depends` when an asyncio loop is already running, optional allowlisted gateway → Streamlit **HTTP** headers, richer `fluxlit doctor` / cookbook docs) is in **0.10.0** — see **Current status (0.11.x)** above.

**Theme:** Bring **optional**, FastAPI-style **type annotations** and **Pydantic (or `TypedDict`) models** to Streamlit integrations so teams can express page metadata, inputs, and shared dependencies explicitly — without breaking existing `(st, client) -> None` handlers.

### Page returns and layout metadata

| Feature | Description |
|---------|-------------|
| **`Page` / `PageMeta` return types** | Handlers may return a small Pydantic model or `TypedDict` describing **title**, **icon**, **layout** (`wide` / `centered`), **order**, breadcrumbs, default query params, etc.; FluxLit applies it via `set_page_config` / nav builders in a generated wrapper (parallel to FastAPI `response_model` / response shaping). |
| **`None` remains the default** | Untyped or `-> None` pages behave as today; returning metadata is strictly opt-in. |
| **Optional setup/teardown** | Explore `yield` / context-manager patterns for one-time setup around a run where they align with Streamlit’s rerun model (document limitations clearly). |

### Dependency injection (`Annotated` / `Depends`)

| Feature | Description |
|---------|-------------|
| **`Depends` for pages** | Inspect page signatures beyond `(st, client)` to inject **`FluxlitSettings`**, **`FluxLitPublicUrls`**, **`FluxLit`**, **`ApiClient`**, **`SessionStore`**, OIDC/token factories, etc. — same mental model as FastAPI, all optional. |
| **`Annotated[..., Header()]` / `Cookie()`** | Where meaningful for **internal** or forwarded context (e.g. correlation id via `ContextVar` from the gateway), mirror FastAPI parameter metadata for docs and tests. |
| **Shared claims DTO** | Optional injection of a **validated user / claims** object (Pydantic or `TypedDict`) aligned with FastAPI route dependencies so UI code does not parse JWTs manually (extends **Version 0.3** “claims in page functions” intent). |

### Query params, session state, and URL-session blobs

| Feature | Description |
|---------|-------------|
| **`QueryModel(BaseModel)`** | Validate `st.query_params` into a model with field errors surfaced in the UI; helpers compose with **`match_nav_page`** / multipage deep links (`docs/deep-links.md`). |
| **`Annotated[..., Query()]`** | Per-field defaults and descriptions for query binding (primarily for IDE/docs and test contracts). |
| **`SessionModel` / typed `session_state`** | Optional `model_validate` / `model_dump` bridge for declared keys in `st.session_state` (strict vs permissive `extra` policy configurable). |
| **Typed URL-session payloads** | Typed hydrate/persist for URL-bound session blobs instead of only `dict[str, JsonValue]`. |

### Multipage navigation as data

| Feature | Description |
|---------|-------------|
| **`PageSpec` / `NavigationModel`** | Declarative tree (path, title, children, sections) generated from registered handlers or declared once and wired to **`st.navigation`**. |
| **Nav from return type** | Optional **`Page` with `children=[...]`** feeding the nav tree while bodies stay imperative. |

### Tooling, testing, and static analysis

| Feature | Description |
|---------|-------------|
| **Page manifest (machine-readable)** | Introspected JSON (or similar) listing paths, titles, parameter names/types (as strings), dependencies used — for **docs**, **admin indexes**, **link checkers**, and **codegen**; not required at runtime. |
| **`@app.page` overloads / richer `Protocol`s** | Stronger static types for `PageFn`, multipage variants, and return-type unions so **mypy/pyright** catch drift (`Page` vs `None`, etc.). |
| **`FluxLitTestClient` / AppTest** | Typed helpers for asserting structured return metadata, validated query models, and injected fakes for `Depends` in tests. |
| **Strict registration mode** | Optional flag to **fail at import** on unknown parameter types or unsupported signatures for teams that want hard contracts. |
| **Docstring → manifest summary** | Reuse function docstrings as short **descriptions** in the page manifest (FastAPI-style). |
| **Tags / groups for pages** | Optional grouping in the manifest for large apps (parallel to OpenAPI tags). |

### Settings and generics (advanced)

| Feature | Description |
|---------|-------------|
| **`FluxLit[SettingsT]` (optional)** | Generic app type when authors subclass **`FluxlitSettings`** for stronger typing end-to-end. |
| **Typed internal env contract** | Narrow or document `FLUXLIT_*` subsets relevant to pages (e.g. feature flags) as small read-only dataclasses where useful. |

### Documentation & migration

| Feature | Description |
|---------|-------------|
| **Guide: “FastAPI patterns in Streamlit pages”** | New doc bridging routes vs pages: return models, `Depends`, query validation, session typing, and when **not** to force typing (Streamlit rerun caveats). |
| **`0.8 → 0.9` upgrade notes** | Changelog entries for any new optional defaults, deprecations, or manifest-related CLI flags. |

### Success criteria (0.9)

- Existing apps **require no code changes** unless they opt into new decorators / return types / `Depends`.
- At least one **reference example** demonstrates **returned `Page` metadata**, one **`QueryModel`**, and one **`Depends`** injection alongside classic `(st, client)`.
- **Mypy** (strict) remains clean for `src/fluxlit`; public typing helpers are covered by tests and documented in the support matrix.
- **Page manifest** (if shipped) is versioned or clearly marked experimental so CI and external tools can rely on field stability.

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
- Optional **`fluxlit[auth]`** installs audited auth dependencies with pinned lower bounds.

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

**Tracking:** the prioritized Phase 4 slice landed in **Version 0.5** above. Remaining work is now later 0.x / pre-1.0 hardening: broader load/chaos evidence, deeper OpenTelemetry hooks, and more deployment recipes.

### Features

- **Health and readiness** for Kubernetes — liveness (`/api/healthz`) and readiness (`/api/readyz` vs Streamlit) shipped, with operator runbooks and Kubernetes examples.
- **Metrics:** optional Prometheus RED metrics shipped; deeper OpenTelemetry instrumentation remains later 0.x work.
- **Structured logging + tracing** correlation — request IDs and JSON logging helpers shipped; full distributed trace propagation remains later 0.x work.
- **Docker:** generated and reference Dockerfiles use digest-pinned Python slim images and non-root users; read-only root remains documented for platforms that support the needed writable mounts.
- **Kubernetes:** example Deployment, Service, and Ingress references shipped.
- **`root_path` / `X-Forwarded-*`:** first-class docs and tests for subpath deployment are in place; broader proxy matrices remain later 0.x work.

### Success criteria

- One-command container run with documented env vars.
- Load test or soak notes for websocket proxy under concurrent users (baseline) — initial soak tooling exists; broader load and chaos evidence remains later 0.x work.

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
- **`docs`** job (Linux / Python 3.12) uploads `coverage.xml` and runs release-parity checks (Ruff, coverage gate, Mypy, generated snapshots, Sphinx **`-W`**); **`slow-tests`** runs marked subprocess tests; **proxy-smoke** and **e2e** jobs cover Docker nginx and browser stacks.

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

Roadmap **historical** phases (0.3–0.10, Phase 0–6) do not map 1:1 to semver. Expect **0.x** to move quickly until the **Phase 3** RC freeze. **1.0** implies the stability scope in **[Path to 1.0](#path-to-1-0)** — stable CLI/config for documented keys, a published **support matrix**, and semver with deprecations for incompatible changes where practical.

---

## Related documentation

- [README.md](README.md) — install, quick start, CLI, configuration, routing
- [PLAN.md](PLAN.md) — product vision, architecture, risks, deployment goals
