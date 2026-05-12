# Configuration

**Use this guide** to set ports, proxy trust, subpaths (`FLUXLIT_ROOT_PATH`), auth-related env vars, and project defaults in `fluxlit.toml`. **Precedence is always:** CLI flags beat environment variables; env beats the project file; then built-in defaults.

For **TLS at the edge**, **HSTS**, tightening **`FLUXLIT_FORWARDED_ALLOW_IPS`** when **`FLUXLIT_TRUST_PROXY`** is on, and **CSP** notes for Streamlit-heavy apps, see {doc}`production-tls`. For **secrets in logs**, secret managers, and **JWT / OIDC rotation**, see {doc}`secrets`.

(runtime-env)=

## Runtime-managed environment variables

When you use **`fluxlit dev`** or **`fluxlit run`**, the parent process sets additional **`FLUXLIT_*`** variables for the Streamlit subprocess and for code that resolves the proxy target. You typically **should not** override these unless you are doing advanced testing.

| Variable | Purpose |
|----------|---------|
| `FLUXLIT_APP` | Import target for the `FluxLit` instance (e.g. `app:app`). |
| `FLUXLIT_API_PREFIX` | Public API mount path (default `/api`); used when building internal URLs. |
| `FLUXLIT_INTERNAL_API_BASE` | Absolute base URL for {class}`~fluxlit.client.ApiClient` inside Streamlit (includes `/api`). |
| `FLUXLIT_STREAMLIT_UPSTREAM` | Base URL of the Streamlit HTTP server (loopback); used by the gateway proxy and {func}`~fluxlit.health.probe_streamlit_ready`. |
| `FLUXLIT_STREAMLIT_UPSTREAM_FILE` | Path to a file mirroring the upstream URL so Uvicorn reload workers and restarts stay consistent. |

`create_gateway_app` / bare tests may run without the upstream variables; then `GET /readyz` reports `streamlit: not_configured`. See {mod}`fluxlit.runtime` and {doc}`deployment`.

For Pytest and in-process Streamlit `AppTest` patterns, including when to set
`FLUXLIT_APP`, `FLUXLIT_TESTS`, and `FLUXLIT_DISABLE_URL_SESSION`, see
{doc}`testing`.

## Precedence

1. **CLI flags** (highest)
2. **Environment variables** (`FLUXLIT_*`, plus `.env` via Pydantic Settings)
3. **Project file** (`fluxlit.toml` or `[tool.fluxlit]` in `pyproject.toml`)
4. **`FluxlitSettings` field defaults**

## Project file

- **`fluxlit.toml`** in the current working directory (top-level keys), or
- **`[tool.fluxlit]`** in **`pyproject.toml`** if `fluxlit.toml` is missing.

If both exist, **`fluxlit.toml` wins**.

Supported keys include: `target`, `gateway_host`, `gateway_port`, `log_level`, `debug`, `api_mount_path`, `root_path`.

Example `fluxlit.toml`:

```toml
target = "app:app"
gateway_host = "127.0.0.1"
gateway_port = 8000
log_level = "info"
```

## Environment variables

{class}`~fluxlit.config.FluxlitSettings` loads `FLUXLIT_*` variables and optional `.env`.

| Variable | Role |
|----------|------|
| `FLUXLIT_TITLE` | App title (FastAPI / UX default). |
| `FLUXLIT_GATEWAY_HOST` / `FLUXLIT_GATEWAY_PORT` | Bind defaults (CLI still overrides for `dev` / `run`). |
| `FLUXLIT_ROOT_PATH` | Public URL prefix when the app is mounted under a subpath (FastAPI/Uvicorn `root_path`, gateway routing, Streamlit `server.baseUrlPath`). Use the path users see in the browser (e.g. Posit Connect content URL path). |
| `FLUXLIT_TRUST_PROXY` | If true, enable Uvicorn `proxy_headers` and trust `X-Forwarded-*` / client scheme (typical behind Posit Connect, nginx, or Traefik). You can also pass `fluxlit run --proxy-headers`. |
| `FLUXLIT_FORWARDED_ALLOW_IPS` | Uvicorn `forwarded_allow_ips` when proxy headers are enabled; defaults to `*` when trusting the proxy and this is unset. |
| `FLUXLIT_STREAMLIT_PUBLIC_PATH` | Optional subpath used only if `FLUXLIT_ROOT_PATH` is empty; prefer `FLUXLIT_ROOT_PATH`. |
| `FLUXLIT_INTERNAL_API_BASE` | Set by the runtime for Streamlit-side {class}`~fluxlit.client.ApiClient` (should include `/api`). |
| `FLUXLIT_ENABLE_REQUEST_LOGGING` | If true, log API requests (method, path, status) at INFO with request id context. |
| `FLUXLIT_DEBUG` | If true, enable **debug mode**: turns on gateway access logs and API request logging, bumps `log_level` from `info` to `debug` when unchanged, exposes `GET /__fluxlit/debug` (redacted settings plus recent gateway dispatches), emits extra gateway DEBUG lines for path splits, prints a `[fluxlit-debug]` banner on unified startup, and makes `FluxLit.get_client()` propagate `X-Request-ID`. Same as `fluxlit dev` / `run` / `workbench` `--debug`. Must not shadow `api_mount_path` (the debug route is disabled if it would collide). |
| `FLUXLIT_ENABLE_GATEWAY_ACCESS_LOG` | If true, log each **gateway** request at INFO with structured `extra` (`fluxlit_dispatch`, path, redacted `query`, method/type); default is DEBUG-only. See {doc}`observability`. |
| `FLUXLIT_URL_SESSION_QUERY_PARAM` | Query key used by {mod}`fluxlit.url_session` helpers (default **`fluxlit_sid`**); gateway access logs redact this key’s value in the structured `query` field. See {doc}`url-session`. |
| `FLUXLIT_ENABLE_GATEWAY_PROMETHEUS_METRICS` | If true, expose Prometheus text metrics on the gateway (requires `prometheus-client`). See {doc}`observability`. |
| `FLUXLIT_GATEWAY_PROMETHEUS_METRICS_PATH` | HTTP GET path for metrics (default **`/__fluxlit/metrics`**); must not start with `api_mount_path`. |
| `FLUXLIT_GATEWAY_UPSTREAM_CONNECT_TIMEOUT_S` | `httpx` connect timeout (seconds) for gateway → Streamlit HTTP proxy (default **30**). |
| `FLUXLIT_GATEWAY_UPSTREAM_READ_TIMEOUT_S` | `httpx` read timeout (seconds) for that proxy (default **120**). |
| `FLUXLIT_GATEWAY_MAX_PROXY_REQUEST_BODY_BYTES` | Max incoming request body bytes proxied to Streamlit; **0** = unlimited. When exceeded the gateway responds with **413**. |
| `FLUXLIT_GATEWAY_MAX_CONCURRENT_UPSTREAM_HTTP` | Max concurrent in-flight HTTP proxy requests to Streamlit; **0** = no limit (semaphore). |
| `FLUXLIT_GATEWAY_HTTPX_MAX_CONNECTIONS` | When **> 0**, sets `httpx.Limits.max_connections` on the shared gateway `AsyncClient` (**0** = httpx default). |
| `FLUXLIT_GATEWAY_HTTPX_MAX_KEEPALIVE_CONNECTIONS` | When max connections is set, optional keepalive cap (**0** lets httpx derive). |
| `FLUXLIT_GATEWAY_WS_OPEN_TIMEOUT_S` | WebSocket client `open_timeout` (seconds) to the Streamlit upstream (default **30**). |
| `FLUXLIT_GATEWAY_WS_PING_INTERVAL_S` | Optional upstream WebSocket `ping_interval` (unset = library default). |
| `FLUXLIT_GATEWAY_WS_PING_TIMEOUT_S` | Optional upstream `ping_timeout`. |
| `FLUXLIT_GATEWAY_WS_CLOSE_TIMEOUT_S` | Optional upstream `close_timeout`. |
| `FLUXLIT_GATEWAY_WS_MAX_MESSAGE_BYTES` | Optional upstream `max_size` (bytes) for frames; omit or unset for unlimited. |
| `FLUXLIT_UVICORN_GRACEFUL_SHUTDOWN_TIMEOUT_S` | If set, passed to Uvicorn `timeout_graceful_shutdown` for `fluxlit dev` / `fluxlit run` (align with Kubernetes `terminationGracePeriodSeconds`). See {doc}`deployment`. |
| `FLUXLIT_ENABLE_SECURITY_HEADERS` | If true, add baseline security headers on the FastAPI app (HSTS when HTTPS, `X-Content-Type-Options`, etc.). |
| `FLUXLIT_CORS_ALLOW_ORIGINS` | JSON list of allowed origins (e.g. `["http://localhost:3000"]`). Empty list disables CORS middleware. |
| `FLUXLIT_CORS_ALLOW_CREDENTIALS` | Whether to set `Access-Control-Allow-Credentials` when CORS is enabled. |
| `FLUXLIT_CORS_MIDDLEWARE_KWARGS` | JSON object of extra keyword arguments for Starlette `CORSMiddleware` when CORS is enabled (e.g. `{"expose_headers": ["X-My-Header"], "max_age": 600}`). |
| `FLUXLIT_STREAMLIT_RUN_CLI_ARGS` | JSON list of extra `streamlit run` CLI tokens appended after FluxLit’s built-in flags (e.g. `["--theme.base","light"]`). |
| `FLUXLIT_STREAMLIT_PAGE_CONFIG` | JSON object merged into `streamlit.set_page_config` (keys such as `layout`, `page_icon`, `initial_sidebar_state`, `menu_items`; `page_title` defaults from `FLUXLIT_TITLE`). |
| `FLUXLIT_PUBLIC_BASE_URL` | Public origin for OAuth redirects (e.g. `https://app.example.com`), used with BFF/OIDC helpers. Prefer this namespaced variable over `PUBLIC_BASE_URL`. |
| `PUBLIC_BASE_URL` | Compatibility fallback used only when `FLUXLIT_PUBLIC_BASE_URL` is unset. If both are set differently, FluxLit uses `FLUXLIT_PUBLIC_BASE_URL`; `fluxlit doctor` warns, or fails when `FLUXLIT_STRICT_PUBLIC_BASE_URL=1`. |
| `FLUXLIT_STRICT_PUBLIC_BASE_URL` | If true, `fluxlit doctor` treats conflicting `PUBLIC_BASE_URL` / `FLUXLIT_PUBLIC_BASE_URL` values as a failure. |
| `FLUXLIT_JWT_ISSUER` / `FLUXLIT_JWT_AUDIENCE` | Expected JWT `iss` / `aud` when using :meth:`fluxlit.auth.jwt.JWTBearer.from_fluxlit_settings` or :meth:`fluxlit.app.FluxLit.make_jwt_bearer`. |
| `FLUXLIT_JWT_HS256_SECRET` | HS256 secret (dev/small deploys); omit if using JWKS. |
| `FLUXLIT_JWT_JWKS_URL` | JWKS URL for RS256; omit if using HS256 secret. |
| `FLUXLIT_JWT_LEEWAY_SECONDS` | Clock skew leeway for JWT validation (default `0`). |
| `FLUXLIT_OIDC_BFF_SECRET` | Secret for first-party JWTs after OIDC callback; used by :meth:`fluxlit.app.FluxLit.attach_oidc_login` when `first_party_secret` is omitted. |

For a **multi-segment** mount such as **`/apps/my-app`** (nginx, `FLUXLIT_PUBLIC_BASE_URL`, WebSockets, and **`fluxlit doctor`** troubleshooting), see {ref}`path-prefix-apps` in {doc}`production-tls`.

**Passthrough caveats:** Do not use `FLUXLIT_STREAMLIT_RUN_CLI_ARGS` to set sidecar `--server.port`, `--server.address`, or `--server.baseUrlPath` (FluxLit assigns these; overrides break the parent process and gateway). In `FLUXLIT_CORS_MIDDLEWARE_KWARGS`, do not repeat `allow_origins`, `allow_credentials`, `allow_methods`, or `allow_headers` (FluxLit sets those from the dedicated fields; duplicates are ignored). Constructor `fastapi_kwargs` cannot change FastAPI `title` or `root_path`; they always follow `FluxlitSettings` so the API matches the public mount and Streamlit.

Gateway proxy fields also exist on {class}`~fluxlit.config.FluxlitSettings` as `gateway_*` / `uvicorn_graceful_shutdown_timeout_s` for use from Python (e.g. tests or `FluxLit(settings=...)`). JSON log formatting is not configured via env; attach {class}`~fluxlit.logging.JsonLogFormatter` in your logging setup — see {doc}`observability`.

See the {mod}`fluxlit.config` API reference for the full settings model.

### Public URL helpers

Use {attr}`fluxlit.app.FluxLit.urls` when you need **browser-visible** links (Streamlit `st.markdown`, emails, OIDC redirects beyond the built-in BFF):

- **`urls.app_base(request)`** — origin plus the public mount (`FLUXLIT_ROOT_PATH` / `FLUXLIT_STREAMLIT_PUBLIC_PATH`): where Streamlit pages live.
- **`urls.api_base(request)`** — app base plus `FLUXLIT_API_MOUNT_PATH` (default `/api`): where `GET /healthz`, `GET /readyz`, OpenAPI, and Swagger UI are served on the gateway.
- **`urls.for_page` / `urls.page_url(request, path, query=...)`** — deep links under the app base (not under `/api`). `page_url` is a readability alias for the same helper.

When **`FLUXLIT_PUBLIC_BASE_URL`** is an absolute URL with a **path**, that value is used as the app base (for CDNs or fixed public entrypoints). When it is origin-only (e.g. `https://app.example.com`), the configured public mount is appended. If it is unset or not a usable absolute URL, the current request’s scheme and host are used (respecting `X-Forwarded-*` when proxy trust is enabled). For invite-style links and normalized query parsing, see {doc}`deep-links`.

### Auth dependencies

Install JWT/OIDC helpers with:

```bash
pip install "fluxlit[auth]"
```

Core HTTP stack remains unchanged if you skip this extra.

### Metrics dependencies

Gateway Prometheus metrics require:

```bash
pip install "fluxlit[metrics]"
```

If `FLUXLIT_ENABLE_GATEWAY_PROMETHEUS_METRICS=1` is set without that extra,
`fluxlit doctor` reports `fluxlit_metrics_extra` with the install command.

## Reverse proxies (Posit Connect, Workbench, nginx)

For a **subpath** deployment (e.g. `https://server.example.com/content/123/`), set **`FLUXLIT_ROOT_PATH`** to that prefix (no trailing slash), e.g. `/content/123`. FluxLit aligns gateway routing (whether the proxy **strips** the prefix or forwards the **full** public path) and Streamlit `baseUrlPath` for static assets and WebSockets. With `fluxlit run`, Uvicorn uses an empty `root_path` and the runtime injects the public mount into the ASGI scope so **strip-prefix** and **full-path** upstreams both work without doubling the prefix.

Behind a trusted edge proxy, set **`FLUXLIT_TRUST_PROXY=1`** (or `fluxlit run --proxy-headers`) so scheme and host from `X-Forwarded-*` match what browsers use. Tighten **`FLUXLIT_FORWARDED_ALLOW_IPS`** if you do not want to trust all sources (default `*` when proxy trust is on and this is unset).

Set **`FLUXLIT_PUBLIC_BASE_URL`** to the public origin (e.g. `https://server.example.com`) when using OAuth/OIDC so redirects stay on the user-facing URL.

```{note}
Some platforms set a generic `PUBLIC_BASE_URL`. FluxLit accepts it as a fallback for
OAuth redirects, but the namespaced `FLUXLIT_PUBLIC_BASE_URL` wins when both are set.
Run `fluxlit doctor --json` in deployment CI to catch mismatches before release.
```

## API clients in tests

{class}`fluxlit.client.ApiClient` is for Streamlit-side server code. It reads
`FLUXLIT_INTERNAL_API_BASE` and defaults to `http://127.0.0.1:8000/api`, so paths
should be API-relative (`client.get("/users")`, not `client.get("/api/users")`).

For in-process Pytest, prefer {class}`fluxlit.testing.FluxLitTestClient`; it exercises
the gateway prefix without requiring a real port. Use `ApiClient` in tests only when
you intentionally want to test the HTTP client wrapper itself.
