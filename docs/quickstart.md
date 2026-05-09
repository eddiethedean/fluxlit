# Quick start

## Install

```bash
pip install fluxlit
```

For contributors working on FluxLit itself:

```bash
git clone https://github.com/eddiethedean/fluxlit.git
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

### Secured routes (JWT and similar)

The `client` injected into `@app.page` handlers has **no** `Authorization` header. Use it for public endpoints or for logging in; for routes protected with {class}`~fluxlit.jwt_auth.JWTBearer` (or your own dependency), create a client that adds the bearer on every request:

```python
from fluxlit.client import ApiClient

@app.page("/account")
def account(st, client):
    token = st.session_state.get("access_token")
    if not token:
        st.info("Sign in first.")
        return
    with ApiClient.for_fluxlit(bearer_token=token) as api:
        st.write(api.get("/me").json())
```

Install **`fluxlit[auth]`** for JWT/OIDC helpers. Full patterns (env-driven `make_jwt_bearer`, OIDC BFF, `prepare_streamlit_api_client`, `auth_header_factory`) are in {doc}`auth-recipes` and {doc}`migration-auth`. A small runnable demo lives in the repo under `examples/reference_auth/`.

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
