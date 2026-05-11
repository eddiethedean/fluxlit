# Changelog

## Unreleased

- **Tests / CI:** coverage job enforces **`--cov-fail-under=80`**; optional **`ty-check`** job (continue-on-error); E2E uploads **Playwright traces** on failure; weekly **`soak-scheduled`** workflow exercises `scripts/soak_http.sh` against `http.server`; shared fixtures **`gateway_test_client_factory`** / **`requires_streamlit_apptest`**; gateway header-filter, Prometheus counter, readiness (`302` / `readyz` 404), WebSocket **`slow`** reconnect stress, and **`DictSessionStore`** contract tests.
- **URL session (Phase 2 follow-on):** `fluxlit.url_session` (`SessionStore`, `InMemorySessionStore`, `ensure_url_session`, `hydrate_url_session`, `persist_url_session`) for refresh continuity **without cookies**; user guide **`docs/url-session.md`**; AppTest + unit tests.
- **Gateway logs:** structured `query` field on gateway access / debug logs with **redacted** session query values (`fluxlit_sid` and `FLUXLIT_URL_SESSION_QUERY_PARAM`); new `FluxlitSettings.url_session_query_param`.
- **Kubernetes:** `examples/kubernetes/ingress.example.yaml` reference Ingress (not applied by default).
- **Supply chain & containers:** CI uploads a **CycloneDX** SBOM (`cyclonedx-sbom` artifact) alongside **`pip-audit`** on `.[auth]`; `fluxlit build`, `examples/docker_compose`, and `docker/proxy-deployment` use **digest-pinned** Python slim and **non-root** `appuser`; Compose example adds **`requirements.in` / `requirements.txt`** via **`pip-compile`**.
- **Docs:** **`docs/production-tls.md`** (TLS, HSTS, `forwarded_allow_ips`, CSP notes), **`docs/secrets.md`** (logs, secret stores, JWT/OIDC rotation); cross-links from README, index, deployment, configuration, security, observability, auth-recipes, troubleshooting, architecture, quickstart, testing, CONTRIBUTING, example READMEs, and **`ROADMAP.md`** security row status.
- **0.5 roadmap / production hardening:** **`examples/kubernetes/`** reference manifests; deployment scaling + multi-worker docs; **`docs/runbooks.md`**; **`docs/support-matrix.md`**; **`scripts/soak_http.sh`**; **`upgrade-smoke`** workflow; OpenAPI **contract** test; optional gateway **Prometheus** metrics (`fluxlit[metrics]`); observability updates (RED metrics, traceparent recipe, correlation limits).
- **Configuration:** `FluxlitSettings` / `FluxLit` passthroughs for Streamlit (`streamlit_run_cli_args`, `streamlit_page_config` → `st.set_page_config`) and Starlette `CORSMiddleware` (`cors_middleware_kwargs`); `fastapi_kwargs` documented as the full `FastAPI(...)` hook.
- **Gateway / operations:** authoritative `X-Request-ID` on proxied HTTP and WebSocket to Streamlit; `FluxlitSettings` for upstream connect/read timeouts, max proxied request body (**413**), concurrent upstream HTTP cap, shared `httpx.AsyncClient` connection limits, WebSocket open/ping/close/`max_size` tuning; `uvicorn_graceful_shutdown_timeout_s` wired into `fluxlit dev` / `fluxlit run` Uvicorn config when set.
- **Logging:** `fluxlit.logging.JsonLogFormatter` (stdlib JSON, merges `extra` fields).
- **Docs:** `docs/observability.md` (correlation diagram, JSON `dictConfig`, SLO/alerting sketches), `docs/deployment.md` (Kubernetes graceful shutdown), `docs/configuration.md` gateway env table; README, index, quickstart, architecture, testing cross-links.
- **Tests:** gateway correlation integration and proxy robustness modules; expanded `test_logging_json` / `test_config_settings`; `test_streamlit_page_config`; FastAPI `openapi_url` / CORS `expose_headers` coverage; unified lifespan asserting Streamlit argv includes `streamlit_run_cli_args`.
- **Safety:** Reject `streamlit_run_cli_args` that override sidecar port/address/baseUrlPath; strip CORS middleware kwargs that duplicate FluxLit-controlled keys; always set FastAPI `title` / `root_path` from settings after `fastapi_kwargs` merge.

## 0.5.0

- **ASGI / Uvicorn:** `FluxLit` is a first-class ASGI app (`uvicorn app:app`); unified stack via `asgi_from_fluxlit` / `create_unified_app` with lifespan bridged to the inner FastAPI app, Streamlit sidecar lifecycle, and spec-shaped HTTP/WebSocket error responses.
- **Imports:** `load_fluxlit` prefers a local `./<module>.py` when resolving targets (avoids `app.py` / `PYTHONPATH` shadowing); optional `FluxLit(import_target=...)` for explicit `module:attr`.
- **CLI:** `fluxlit new` writes `fluxlit.toml` with `target` and `gateway_port`; mentions `uvicorn app:app`.
- **Tests:** `tests/test_asgi_unified.py` for lifespan, concurrent HTTP, streaming request bodies, sidecar failure, and related edge cases.
- **Docs / roadmap:** Quickstart and deployment document the simple Uvicorn entrypoint; **ROADMAP** adds planned **Version 0.5** production-hardening themes and ties **Phase 4** delivery to that track.

## 0.4.1

- **Docs:** Fix PyPI version badge image URL in `README.md` (use Shields `pypi/v` badge).

## 0.4.0

- **Runtime (Windows):** ``fluxlit shutdown`` / ``shutdown_unified_process`` use ``taskkill /T`` instead of ``os.kill(SIGTERM)``; ``--force`` uses ``taskkill /T /F``. PID liveness uses ``OpenProcess`` (avoids locale-dependent ``tasklist`` parsing).
- **Readiness:** ``GET /api/readyz`` / ``fluxlit.health.probe_streamlit_ready`` require a **2xx** response from the Streamlit upstream root (stricter than treating any status below 500 as ready).
- **Gateway:** Return **502** when the Streamlit upstream URL resolves empty at request time (e.g. missing state file); WebSocket connections get a clear close when upstream is missing.
- **Dev:** On ``--reload-scope=full``, if the new Streamlit process does not open its port in time, terminate it, print stderr guidance, and stop the gateway.
- **CI:** Docs job runs ``sphinx-build -W`` (warnings as errors).
- **Docs:** Windows ``shutdown`` behavior (``taskkill``); deployment, observability, and troubleshooting updates for readiness behavior.
- **Runtime:** Map IPv6 unspecified bind ``::`` to loopback for ``FLUXLIT_INTERNAL_API_BASE`` (same as ``0.0.0.0``).
- **OIDC BFF:** Validate ``id_token`` with IdP JWKS when using ``GenericOIDCClient``; optional ``OIDCBFFConfig.id_token_audience`` / ``id_token_leeway_seconds``; parse-only fallback for other ``OIDCProvider`` stubs.
- **JWT:** Run PyJWT/JWKS decode in a worker thread via ``anyio.to_thread`` to avoid blocking the event loop.
- **Gateway:** Use Latin-1 for stripped ``raw_path``; log exceptions while streaming proxied response bodies.
- **API:** ``FluxLit.attach_oidc_login`` raises if called twice on the same instance.
- **CI:** Release workflow runs ``pip-audit`` (same as main CI); ``slow`` pytest marker; ``slow-tests`` and ``coverage`` jobs (upload ``coverage.xml`` artifact); expanded gateway and auth tests; Playwright E2E including ``FLUXLIT_ROOT_PATH``.
- **Docs:** OIDC in-memory store and JWKS ``id_token`` behavior in security, auth-recipes, and ``SECURITY.md``; fix OIDC docstring cross-reference (Streamlit exchange helpers); README, ``docs/testing.md``, index, roadmap testing table, and cross-links for the test/CI layout.

## 0.3.0

- **Auth (optional `fluxlit[auth]`):** JWT bearer validation with HS256 (dev) or JWKS (RS256/ES256), `RequireScopes` / `RequireRoles`, first-party HS256 minting for BFF flows.
- **OIDC:** `GenericOIDCClient` (OpenID discovery + Authorization Code with PKCE), `register_oidc_bff_routes` with one-time `auth_code` exchange for Streamlit-safe token handoff.
- **Forward auth:** `TrustedProxyUser` / `TrustedProxyUserConfig` with optional HTTPS and client-host checks.
- **Client:** `ApiClient` `default_headers`, `auth_header_factory`, `propagate_request_id`, and `ApiClient.for_fluxlit(bearer_token=...)`.
- **Streamlit:** `exchange_auth_code_from_query`, `bearer_headers_from_session`, `prepare_streamlit_api_client`.
- **Security:** opt-in `FluxlitSettings.enable_security_headers` and CORS (`cors_allow_origins`, `cors_allow_credentials`); `public_base_url` for OAuth redirects; `SECURITY.md` and CI `pip-audit` on `.[auth]`; PyPI `Security` project URL; sdist includes `SECURITY.md`.
- **CLI:** `fluxlit doctor` JWT clock-skew note, OAuth/CORS guidance.
- **Config / UX:** `FLUXLIT_JWT_*`, `FLUXLIT_OIDC_BFF_SECRET`, `jwt_leeway_seconds`; `JWTBearer.from_fluxlit_settings`, `FluxLit.make_jwt_bearer`, `FluxLit.attach_oidc_login`.
- **Docs:** security architecture, auth recipes, migration guide, README quick links and secured-API section, quickstart/index updates; reference example `examples/reference_auth/`; docs extra includes `itsdangerous` for Sphinx.
- **Tests:** JWT/OIDC/BFF/error-path coverage, Streamlit auth helpers, security middleware, `ApiClient` header merging / request-id propagation, friendly security ergonomics tests.

## 0.2.0

- **Config:** `fluxlit.toml` and `pyproject.toml` `[tool.fluxlit]` for default `target`, bind options, and log level (`fluxlit.config.project`). Precedence: CLI → environment → project file → defaults.
- **CLI:** `fluxlit build` writes a starter `Dockerfile` and `.dockerignore`; `fluxlit doctor` reports PASS/WARN/FAIL checks (import, port bind, deps, `FLUXLIT_INTERNAL_API_BASE`) with optional `--warnings-only`.
- **CLI:** `fluxlit dev` / `run` accept an omitted `target` when configured in a project file; `--reload-scope=gateway` documents gateway-only reload; stderr warns that Streamlit does not reload.
- **Pages:** `FluxLit.discover_pages(directory, package=...)` imports sibling modules and calls `register(app)` for opt-in multipage packages.
- **Client:** `ApiClient.get_model` / `post_model` for Pydantic-validated JSON.
- **Observability:** Gateway sets a request id from `X-Request-ID` (or generates one) via `logging_context`; optional `FluxlitSettings.enable_request_logging` adds FastAPI access logs at INFO.
- **Dependencies:** `tomli` on Python 3.10 for TOML parsing (stdlib `tomllib` on 3.11+).
- **Docs:** Sphinx + MyST site under `docs/`, optional `pip install -e ".[docs]"`, Read the Docs config (`.readthedocs.yaml`), CI `docs` job, PyPI `Documentation` URL points to RTD; repository planning docs live at `PLAN.md` and `ROADMAP.md`.
- **Testing:** Broader unit and integration tests (gateway edge cases, CLI, `streamlit_main` import paths, `pytest-cov` + Coverage config for the `src/` layout).

## 0.1.0

- Unified gateway + sidecar runtime (single public port; HTTP + WebSocket proxy to Streamlit).
- CLI: `dev`, `run`, `new`, `doctor`.
- Configurable API prefix (`api_mount_path` / gateway `api_prefix`) with `/api` default.
- Runtime hardening (gateway stops if Streamlit exits; improved shutdown behavior).
- Testing support:
  - FluxLit-native `FluxLitTestClient`
  - FastAPI/Starlette TestClient tests for gateway routing
  - Streamlit AppTest coverage (version-dependent)
  - CLI + ApiClient contract tests
- CI (GitHub Actions) and contributor docs.

