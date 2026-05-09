# FluxLit (`fluxlit`)

[![Documentation Status](https://readthedocs.org/projects/fluxlit/badge/?version=stable)](https://fluxlit.readthedocs.io/en/stable/?badge=stable)

Production-oriented unified runtime for **FastAPI** and **Streamlit**: one public port, one CLI, and a single `FluxLit` app object for APIs plus UI pages.

**Documentation (hosted):** [https://fluxlit.readthedocs.io/en/stable/](https://fluxlit.readthedocs.io/en/stable/)

| Topic | Read the Docs |
|--------|----------------|
| Quick start | [Quick start](https://fluxlit.readthedocs.io/en/stable/quickstart.html) |
| Architecture & routing | [Architecture](https://fluxlit.readthedocs.io/en/stable/architecture.html) |
| Config & `fluxlit.toml` | [Configuration](https://fluxlit.readthedocs.io/en/stable/configuration.html) |
| CLI (`dev`, `run`, `doctor`, `build`) | [CLI](https://fluxlit.readthedocs.io/en/stable/cli.html) |
| Testing | [Testing](https://fluxlit.readthedocs.io/en/stable/testing.html) |
| Python API | [API reference](https://fluxlit.readthedocs.io/en/stable/api/index.html) |
| Contributing | [Contributing](https://fluxlit.readthedocs.io/en/stable/contributing.html) |
| Changelog | [Changelog](https://fluxlit.readthedocs.io/en/stable/changelog.html) |
| Roadmap | [Roadmap](https://fluxlit.readthedocs.io/en/stable/roadmap.html) |

**Also in the repo:** [Product & architecture plan](https://github.com/odosmatthews/fluxlit/blob/main/PLAN.md) (source for long-form product context; overview is on Read the Docs under [Architecture](https://fluxlit.readthedocs.io/en/stable/architecture.html)).

---

## Overview

FluxLit targets teams that want FastAPI for HTTP APIs and Streamlit for interactive UIs without wiring separate ports, ad hoc reverse proxies, and brittle dev scripts. The runtime uses a **sidecar model**: Streamlit runs in a subprocess; a **Starlette ASGI gateway** fronts both the API and the UI.

---

## Requirements

- Python **3.10+**
- Dependencies are declared in [`pyproject.toml`](pyproject.toml) (FastAPI, Uvicorn, Streamlit, Typer, httpx, websockets, etc.).

---

## Install

```bash
pip install fluxlit
```

For local development of FluxLit itself:

```bash
git clone https://github.com/odosmatthews/fluxlit.git
cd fluxlit
pip install -e ".[dev]"
```

---

## Quick start

Create a project (optional):

```bash
fluxlit new my-app
cd my-app
```

Define a `FluxLit` app (e.g. `app.py`):

```python
from fluxlit import FluxLit

app = FluxLit(title="Admin Portal")

@app.api.get("/users")
def users():
    return [{"name": "Ada"}]

@app.page("/")
def home(st, client):
    st.title("Dashboard")
    st.write(client.get("/users").json())
```

Run the unified server (default import path `app:app`, or `target` from `fluxlit.toml` / `[tool.fluxlit]`):

```bash
fluxlit dev
# or explicitly:
fluxlit dev app:app
```

- **Browser:** open the URL shown by Uvicorn (default `http://127.0.0.1:8000`).
- **API:** routes are mounted under **`/api`** (e.g. `GET /api/users`).
- **OpenAPI / docs:** `http://127.0.0.1:8000/api/docs` (Swagger) and `/api/openapi.json`.
- **Health:** `http://127.0.0.1:8000/api/healthz` (hidden from OpenAPI).

From Streamlit code, `ApiClient` calls the API using a base URL that includes `/api` (set automatically as `FLUXLIT_INTERNAL_API_BASE` when using `fluxlit dev` / `fluxlit run`). Use paths like `client.get("/users")`, not `client.get("/api/users")`.

For typed JSON responses, use `ApiClient.get_model` / `post_model` with Pydantic models.

---

## How routing works

```text
Browser
   │
   ▼
┌──────────────────────────────────────┐
│  FluxLit gateway (Uvicorn, one port)  │
├──────────────────────────────────────┤
│  /api/*     → FastAPI (path prefix    │
│               stripped inside the app) │
│  /*         → Streamlit (HTTP + WS    │
│               proxy to subprocess)     │
└──────────────────────────────────────┘
```

Anything that is **not** under `/api` is forwarded to Streamlit (including WebSockets used by Streamlit). Reserve **`/api`** for your HTTP API.

Note: the API prefix is configurable via `FluxlitSettings.api_mount_path` (default `/api`).

---

## CLI

| Command | Description |
|--------|-------------|
| `fluxlit dev [target]` | Development server: Streamlit subprocess + gateway. Default `target`: CLI arg → `fluxlit.toml` / `pyproject.toml` `[tool.fluxlit]` → `app:app`. |
| `fluxlit run [target]` | Same stack without auto-reload. |
| `fluxlit doctor [target]` | Environment checks (import, bind, deps, `FLUXLIT_INTERNAL_API_BASE`). Exits non-zero on failures unless `--warnings-only`. |
| `fluxlit build [target]` | Write a starter `Dockerfile` and `.dockerignore` (use `--output` / `-o`, `--force` to overwrite). |
| `fluxlit new <name>` | Scaffold a minimal `app.py` in a new directory. |
| `python -m fluxlit` | Equivalent entry to the `fluxlit` console script. |

Options for `dev` / `run` include `--host`, `--port`, `--log-level`, `--proxy-headers`, `--forwarded-allow-ips`.
`fluxlit dev --reload` reloads the **API gateway process only** via Uvicorn; the Streamlit subprocess is **not** restarted. Use `--reload-scope=gateway` (default) or restart `fluxlit` to pick up Streamlit UI changes.

---

## Configuration

**Precedence:** CLI flags override environment variables; environment overrides project file defaults; then `FluxlitSettings` field defaults.

### Project file

- **`fluxlit.toml`** in the current working directory (top-level keys), or
- **`[tool.fluxlit]`** in **`pyproject.toml`** if `fluxlit.toml` is absent.

If both exist, **`fluxlit.toml` wins**. Supported keys include `target`, `gateway_host`, `gateway_port`, `log_level`, `api_mount_path`, and `root_path`.

Example `fluxlit.toml`:

```toml
target = "app:app"
gateway_host = "127.0.0.1"
gateway_port = 8000
log_level = "info"
```

### Environment (`FluxlitSettings`)

See [Configuration](https://fluxlit.readthedocs.io/en/stable/configuration.html) and the [API reference](https://fluxlit.readthedocs.io/en/stable/api/index.html) (`fluxlit.config`). Variables use the **`FLUXLIT_`** prefix and optional **`.env`** file.

| Variable | Role |
|----------|------|
| `FLUXLIT_TITLE` | App title (default for FastAPI / UX). |
| `FLUXLIT_GATEWAY_HOST` / `FLUXLIT_GATEWAY_PORT` | Defaults for binding (also used in settings; CLI overrides bind for dev/run). |
| `FLUXLIT_ROOT_PATH` | ASGI root path behind a reverse proxy (passed through to FastAPI). |
| `FLUXLIT_INTERNAL_API_BASE` | Set by the runtime for Streamlit-side `ApiClient` (includes `/api`). |
| `FLUXLIT_ENABLE_REQUEST_LOGGING` | If true, log each API request (method, path, status) at INFO with request id context. |

---

## Suggested project layout

```text
my_app/
├── app.py              # FluxLit instance, @app.api routes, @app.page handlers
├── pkg/                # Optional: Python package for discover_pages
│   ├── __init__.py
│   └── pages/          # call discover_pages("pages", package="pkg")
│       ├── __init__.py
│       └── reports.py  # def register(app): @app.page(...) ...
├── services/
├── static/
├── fluxlit.toml        # Optional defaults for CLI
└── .env                # FLUXLIT_* and secrets (do not commit)
```

**Optional page packages:** each `pkg/pages/*.py` module may define `register(app: FluxLit) -> None` that attaches `@app.page` handlers; call `app.discover_pages("pages", package="pkg")` after constructing `FluxLit`.

---

## Package layout (`src/fluxlit`)

Autogenerated detail: [Python API reference](https://fluxlit.readthedocs.io/en/stable/api/index.html). Summary:

| Module | Purpose |
|--------|---------|
| `app` | `FluxLit` application object |
| `cli` | Typer CLI |
| `client` | `ApiClient` (httpx) for server-side API calls |
| `config` | `FluxlitSettings` |
| `gateway` | ASGI router + HTTP/WebSocket proxy (request id context + debug logs) |
| `project_config` | `fluxlit.toml` / `[tool.fluxlit]` loading |
| `logging_context` | Request id `ContextVar` for gateway / API |
| `runtime` | Subprocess orchestration, Uvicorn entry |
| `streamlit_main` | Streamlit entry script (`FLUXLIT_APP`) |
| `testing` | `FluxLitTestClient` (FluxLit-native API + Streamlit test helpers) |
| `api` | Optional `APIRouter` helpers |
| `auth` | Placeholder / future shared auth hooks |

---

## Testing

FluxLit uses the same “built-in” testing platforms you likely already know:

- **FastAPI**: `starlette.testclient.TestClient`
- **Streamlit**: `streamlit.testing.v1.AppTest` (version-dependent)

FluxLit also ships a small wrapper: **`FluxLitTestClient`**.

```python
from fluxlit import FluxLit, FluxLitTestClient

app = FluxLit(title="Test")
client = FluxLitTestClient(app)

assert client.api_get("/healthz").status_code == 200
```

For Streamlit, you can run FluxLit’s Streamlit entrypoint via AppTest:

```python
at = client.streamlit(target="my_app:app", extra_sys_path=".")
```

---

## Development (contributors)

See [Contributing](https://fluxlit.readthedocs.io/en/stable/contributing.html) on Read the Docs for setup, docs builds, and PR expectations.

```bash
pip install -e ".[dev]"
ruff check src tests && ruff format src tests
python -m pytest
python -m mypy src/fluxlit
```

---

## Features: today vs planned

**Available in current alphas**

- Single public port; managed Streamlit subprocess
- Gateway: `/api` → FastAPI; HTTP + WebSocket proxy to Streamlit
- `@app.page` + `st.navigation` integration; optional `discover_pages` for package layouts
- `fluxlit new`, `dev`, `run`, `doctor`, `build`
- `fluxlit.toml` / `[tool.fluxlit]` project defaults; `ApiClient.get_model` / `post_model`
- Request id propagation (`X-Request-ID`) and optional API access logging
- Typed package; Ruff + Mypy + Pytest in-tree; CI on GitHub Actions

**Planned** (see [Roadmap on Read the Docs](https://fluxlit.readthedocs.io/en/stable/roadmap.html))

- Hardened reload (Streamlit lifecycle), first-class health/metrics
- Auth (JWT, sessions, proxy headers, OAuth)
- Official Docker/Kubernetes examples beyond `fluxlit build` templates
- OpenAPI-generated client (optional)

---

## Philosophy

FluxLit should stay **Pythonic** (explicit, typed, easy to reason about), **production-minded** (proxy-safe, observable, deployable), and **honest** about Streamlit’s process/WebSocket model until a native ASGI path is proven.

---

## License

MIT — see [`pyproject.toml`](pyproject.toml) metadata.
