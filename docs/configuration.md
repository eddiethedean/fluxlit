# Configuration

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
| `FLUXLIT_ROOT_PATH` | ASGI root path behind a reverse proxy (passed to FastAPI). |
| `FLUXLIT_INTERNAL_API_BASE` | Set by the runtime for Streamlit-side {class}`~fluxlit.client.ApiClient` (should include `/api`). |
| `FLUXLIT_ENABLE_REQUEST_LOGGING` | If true, log API requests (method, path, status) at INFO with request id context. |
| `FLUXLIT_ENABLE_SECURITY_HEADERS` | If true, add baseline security headers on the FastAPI app (HSTS when HTTPS, `X-Content-Type-Options`, etc.). |
| `FLUXLIT_CORS_ALLOW_ORIGINS` | JSON list of allowed origins (e.g. `["http://localhost:3000"]`). Empty list disables CORS middleware. |
| `FLUXLIT_CORS_ALLOW_CREDENTIALS` | Whether to set `Access-Control-Allow-Credentials` when CORS is enabled. |
| `FLUXLIT_PUBLIC_BASE_URL` | Public origin for OAuth redirects (e.g. `https://app.example.com`), used with BFF/OIDC helpers. |

See the {mod}`fluxlit.config` API reference for the full settings model.

### Auth dependencies

Install JWT/OIDC helpers with:

```bash
pip install "fluxlit[auth]"
```

Core HTTP stack remains unchanged if you skip this extra.
