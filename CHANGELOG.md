# Changelog

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

- **Config:** `fluxlit.toml` and `pyproject.toml` `[tool.fluxlit]` for default `target`, bind options, and log level (`fluxlit.project_config`). Precedence: CLI → environment → project file → defaults.
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

## Unreleased

- **Dev:** `fluxlit dev --reload --reload-scope=full` restarts the Streamlit sidecar on file changes (`watchfiles`); `gateway` remains the default (Uvicorn reload only).
- **Gateway:** Optional per-request `upstream_resolver` and temp-file upstream state so reload workers and Streamlit restarts stay consistent; optional `enable_gateway_access_log` (structured INFO logs).
- **API:** `GET /api/readyz` readiness probe for the Streamlit upstream (see `fluxlit.health`).
- **CLI:** `fluxlit doctor` JWT clock skew only when JWT/OIDC env is present; `fluxlit_auth_extra` check; proxy_headers PASS when `trust_proxy` matches subpath deployment; clearer OAuth base URL warning.
- **Utilities:** `fluxlit.logging_redact` for safe header logging.
- **Docs:** `docs/observability.md`, `docs/rate-limiting.md`; auth-recipes BFF refresh subsection; CLI/reload and README updates.
- **Examples:** `examples/docker_compose/` minimal Compose stack.
- **Dependencies:** direct `watchfiles` dependency.
