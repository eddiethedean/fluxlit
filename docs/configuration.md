# Configuration

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

## Precedence

1. **CLI flags** (highest)
2. **Environment variables** (`FLUXLIT_*`, plus `.env` via Pydantic Settings)
3. **Project file** (`fluxlit.toml` or `[tool.fluxlit]` in `pyproject.toml`)
4. **`FluxlitSettings` field defaults**

## Project file

- **`fluxlit.toml`** in the current working directory (top-level keys), or
- **`[tool.fluxlit]`** in **`pyproject.toml`** if `fluxlit.toml` is missing.

If both exist, **`fluxlit.toml` wins**.

Supported keys include: `target`, `gateway_host`, `gateway_port`, `log_level`, `api_mount_path`, `root_path`.

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
| `FLUXLIT_ENABLE_GATEWAY_ACCESS_LOG` | If true, log each **gateway** request at INFO with structured `extra` (`fluxlit_dispatch`, path, method/type); default is DEBUG-only. See {doc}`observability`. |
| `FLUXLIT_ENABLE_SECURITY_HEADERS` | If true, add baseline security headers on the FastAPI app (HSTS when HTTPS, `X-Content-Type-Options`, etc.). |
| `FLUXLIT_CORS_ALLOW_ORIGINS` | JSON list of allowed origins (e.g. `["http://localhost:3000"]`). Empty list disables CORS middleware. |
| `FLUXLIT_CORS_ALLOW_CREDENTIALS` | Whether to set `Access-Control-Allow-Credentials` when CORS is enabled. |
| `FLUXLIT_PUBLIC_BASE_URL` | Public origin for OAuth redirects (e.g. `https://app.example.com`), used with BFF/OIDC helpers. |
| `FLUXLIT_JWT_ISSUER` / `FLUXLIT_JWT_AUDIENCE` | Expected JWT `iss` / `aud` when using :meth:`fluxlit.jwt_auth.JWTBearer.from_fluxlit_settings` or :meth:`fluxlit.app.FluxLit.make_jwt_bearer`. |
| `FLUXLIT_JWT_HS256_SECRET` | HS256 secret (dev/small deploys); omit if using JWKS. |
| `FLUXLIT_JWT_JWKS_URL` | JWKS URL for RS256; omit if using HS256 secret. |
| `FLUXLIT_JWT_LEEWAY_SECONDS` | Clock skew leeway for JWT validation (default `0`). |
| `FLUXLIT_OIDC_BFF_SECRET` | Secret for first-party JWTs after OIDC callback; used by :meth:`fluxlit.app.FluxLit.attach_oidc_login` when `first_party_secret` is omitted. |

See the {mod}`fluxlit.config` API reference for the full settings model.

### Auth dependencies

Install JWT/OIDC helpers with:

```bash
pip install "fluxlit[auth]"
```

Core HTTP stack remains unchanged if you skip this extra.

## Reverse proxies (Posit Connect, Workbench, nginx)

For a **subpath** deployment (e.g. `https://server.example.com/content/123/`), set **`FLUXLIT_ROOT_PATH`** to that prefix (no trailing slash), e.g. `/content/123`. FluxLit aligns gateway routing (whether the proxy **strips** the prefix or forwards the **full** public path) and Streamlit `baseUrlPath` for static assets and WebSockets. With `fluxlit run`, Uvicorn uses an empty `root_path` and the runtime injects the public mount into the ASGI scope so **strip-prefix** and **full-path** upstreams both work without doubling the prefix.

Behind a trusted edge proxy, set **`FLUXLIT_TRUST_PROXY=1`** (or `fluxlit run --proxy-headers`) so scheme and host from `X-Forwarded-*` match what browsers use. Tighten **`FLUXLIT_FORWARDED_ALLOW_IPS`** if you do not want to trust all sources (default `*` when proxy trust is on and this is unset).

Set **`FLUXLIT_PUBLIC_BASE_URL`** to the public origin (e.g. `https://server.example.com`) when using OAuth/OIDC so redirects stay on the user-facing URL.
