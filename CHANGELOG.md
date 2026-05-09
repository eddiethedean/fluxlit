# Changelog

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

- **Auth (optional `fluxlit[auth]`):** JWT bearer validation with HS256 (dev) or JWKS (RS256/ES256), `RequireScopes` / `RequireRoles`, first-party HS256 minting for BFF flows.
- **OIDC:** `GenericOIDCClient` (OpenID discovery + Authorization Code with PKCE), `register_oidc_bff_routes` with one-time `auth_code` exchange for Streamlit-safe token handoff.
- **Forward auth:** `TrustedProxyUser` / `TrustedProxyUserConfig` with optional HTTPS and client-host checks.
- **Client:** `ApiClient` `default_headers`, `auth_header_factory`, `propagate_request_id`, and `ApiClient.for_fluxlit(bearer_token=...)`.
- **Streamlit:** `exchange_auth_code_from_query`, `bearer_headers_from_session`.
- **Security:** opt-in `FluxlitSettings.enable_security_headers` and CORS (`cors_allow_origins`, `cors_allow_credentials`); `public_base_url` for OAuth redirects.
- **CLI:** `fluxlit doctor` JWT clock-skew note, OAuth/CORS guidance.
- **Docs:** security architecture, migration guide, reference example under `examples/reference_auth/`.
- **Tests:** broader JWT/OIDC/BFF/error-path coverage, Streamlit auth helpers, security middleware, and `ApiClient` header merging / request-id propagation.
- **UX:** `FluxlitSettings` gains `FLUXLIT_JWT_*` and `FLUXLIT_OIDC_BFF_SECRET`; `JWTBearer.from_fluxlit_settings`, `FluxLit.make_jwt_bearer`, `FluxLit.attach_oidc_login`, and `prepare_streamlit_api_client` for less boilerplate (docs updated).
- **Docs / README:** Docs table and new README section on calling secured APIs from Streamlit; quickstart + docs index explain injected `client` vs `for_fluxlit` / `prepare_streamlit_api_client`; features list and package table reflect shipped auth modules; auth-recipes and security cross-link the reference example.
- **Security:** Add `SECURITY.md` (supported versions, private reporting, `pip-audit` usage); CI `security-audit` job runs `pip-audit` after installing `.[auth]` (runtime-relevant tree); sdist includes `SECURITY.md`.
