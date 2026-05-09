# FluxLit (`fluxlit`)

Production-oriented unified runtime for **FastAPI** and **Streamlit**: one public port, one CLI, and a single `FluxLit` app object for APIs plus UI pages.

**Docs in this repo:** [Product & architecture plan](FLUXLIT_PLAN.md) · [Development roadmap](FLUXLIT_ROADMAP.md)

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

Run the unified server (default import path `app:app`):

```bash
fluxlit dev app:app
```

- **Browser:** open the URL shown by Uvicorn (default `http://127.0.0.1:8000`).
- **API:** routes are mounted under **`/api`** (e.g. `GET /api/users`).
- **OpenAPI / docs:** `http://127.0.0.1:8000/api/docs` (Swagger) and `/api/openapi.json`.
- **Health:** `http://127.0.0.1:8000/api/healthz` (hidden from OpenAPI).

From Streamlit code, `ApiClient` calls the API using a base URL that includes `/api` (set automatically as `FLUXLIT_INTERNAL_API_BASE` when using `fluxlit dev` / `fluxlit run`). Use paths like `client.get("/users")`, not `client.get("/api/users")`.

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
| `fluxlit dev [target]` | Development server: Streamlit subprocess + gateway. Default `target` is `app:app`. |
| `fluxlit run [target]` | Same stack without auto-reload. |
| `fluxlit new <name>` | Scaffold a minimal `app.py` in a new directory. |
| `python -m fluxlit` | Equivalent entry to the `fluxlit` console script. |

Options for `dev` / `run` include `--host`, `--port`, `--log-level`, `--proxy-headers`, `--forwarded-allow-ips`.
`fluxlit dev` also supports `--reload` (experimental; API gateway reload may not restart Streamlit).

---

## Configuration

`FluxlitSettings` ([`src/fluxlit/config.py`](src/fluxlit/config.py)) loads from environment variables prefixed with **`FLUXLIT_`** and from a **`.env`** file if present.

| Variable | Role |
|----------|------|
| `FLUXLIT_TITLE` | App title (default for FastAPI / UX). |
| `FLUXLIT_GATEWAY_HOST` / `FLUXLIT_GATEWAY_PORT` | Defaults for binding (also used in settings; CLI overrides bind for dev/run). |
| `FLUXLIT_ROOT_PATH` | ASGI root path behind a reverse proxy (passed through to FastAPI). |
| `FLUXLIT_INTERNAL_API_BASE` | Set by the runtime for Streamlit-side `ApiClient` (includes `/api`). |

---

## Suggested project layout

```text
my_app/
├── app.py              # FluxLit instance, @app.api routes, @app.page handlers
├── pages/              # Optional: extra Streamlit modules if you extend beyond @app.page
├── services/
├── static/
└── .env                # FLUXLIT_* and secrets (do not commit)
```

A committed **`fluxlit.toml`** (or similar) config file is on the [roadmap](FLUXLIT_ROADMAP.md); today, prefer env / `.env` and CLI flags.

---

## Package layout (`src/fluxlit`)

| Module | Purpose |
|--------|---------|
| `app` | `FluxLit` application object |
| `cli` | Typer CLI |
| `client` | `ApiClient` (httpx) for server-side API calls |
| `config` | `FluxlitSettings` |
| `gateway` | ASGI router + HTTP/WebSocket proxy |
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
- `@app.page` + `st.navigation` integration
- `fluxlit new`, `dev`, `run`
- Typed package; Ruff + Mypy + Pytest in-tree

**Planned** (see [roadmap](FLUXLIT_ROADMAP.md))

- CI, hardened reload/shutdown, first-class health/metrics
- Auth (JWT, sessions, proxy headers, OAuth)
- Docker/Kubernetes examples, `doctor` / `build` CLI
- Richer config file and optional page discovery

---

## Philosophy

FluxLit should stay **Pythonic** (explicit, typed, easy to reason about), **production-minded** (proxy-safe, observable, deployable), and **honest** about Streamlit’s process/WebSocket model until a native ASGI path is proven.

---

## License

MIT — see [`pyproject.toml`](pyproject.toml) metadata.
