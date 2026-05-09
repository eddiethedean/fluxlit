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

See the {mod}`fluxlit.config` API reference for the full settings model.
