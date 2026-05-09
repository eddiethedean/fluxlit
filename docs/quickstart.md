# Quick start

## Install

```bash
pip install fluxlit
```

For contributors working on FluxLit itself:

```bash
git clone https://github.com/odosmatthews/fluxlit.git
cd fluxlit
pip install -e ".[dev]"
```

## Scaffold (optional)

```bash
fluxlit new my-app
cd my-app
```

## Minimal app

Create `app.py`:

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

## Run

Default import path is `app:app`, or set `target` in `fluxlit.toml` / `pyproject.toml` `[tool.fluxlit]`:

```bash
fluxlit dev
# or
fluxlit dev app:app
```

- Open the URL Uvicorn prints (default `http://127.0.0.1:8000`).
- **API:** `GET /api/users` (prefix configurable via {attr}`~fluxlit.config.FluxlitSettings.api_mount_path`).
- **OpenAPI:** `/api/docs`, `/api/openapi.json`.
- **Health:** `/api/healthz` (hidden from OpenAPI).

## Calling the API from Streamlit

`ApiClient` uses a base URL that includes `/api` (set as `FLUXLIT_INTERNAL_API_BASE` by the runtime). Use paths like `client.get("/users")`, not `client.get("/api/users")`.

For Pydantic-validated JSON, use {meth}`~fluxlit.client.ApiClient.get_model` and {meth}`~fluxlit.client.ApiClient.post_model`.

## Project layout

```text
my_app/
├── app.py
├── pkg/                 # optional: discover_pages("pages", package="pkg")
│   ├── __init__.py
│   └── pages/
│       ├── __init__.py
│       └── reports.py   # def register(app): ...
├── fluxlit.toml         # optional CLI defaults
└── .env                 # secrets (do not commit)
```

See {doc}`configuration` and {doc}`cli` for flags, env vars, and commands.
