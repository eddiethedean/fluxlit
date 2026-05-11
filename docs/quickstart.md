# Quick start

**Goal:** run a tiny app where **Streamlit** shows data from a **FastAPI** route, both on **one URL** (default `http://127.0.0.1:8000`).

```{tip}
**Common gotcha:** inside `@app.page` handlers, use `client.get("/users")`, not `client.get("/api/users")`. The client already points at the API prefix.
```

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

```{note}
Contributor tests: `python -m pytest -n auto -m "not slow"`. More in {doc}`testing`.
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

From the directory that contains `app.py`:

```bash
fluxlit dev
# or, if your module path differs:
fluxlit dev app:app
```

**Or** run it like a normal FastAPI project (same `app` object):

```bash
uvicorn app:app --host 127.0.0.1 --port 8000
```

A :class:`~fluxlit.app.FluxLit` instance **is** an ASGI application: Uvicorn calls it directly—no `--factory` and no `FLUXLIT_APP` env var required when your file is `app.py` and the variable is `app` (the default `target` is `app:app`). If your module is named differently (e.g. `main.py`), set **`target = "main:app"`** in `fluxlit.toml`, or pass ``import_target="main:app"`` to :class:`~fluxlit.app.FluxLit`, or set ``FLUXLIT_APP``.

Put **`gateway_port`** in `fluxlit.toml` (or **`FLUXLIT_GATEWAY_PORT`**) to match Uvicorn’s **`--port`** when it is not **8000**, so the Streamlit sidecar can reach the API.

Advanced / legacy: ``uvicorn fluxlit.runtime:create_unified_app --factory`` with ``FLUXLIT_APP`` still works; prefer ``uvicorn app:app`` for clarity.

FluxLit looks for **`app:app`** by default. You can set **`target`** in `fluxlit.toml` or `pyproject.toml` under **`[tool.fluxlit]`** instead of typing it every time—see {doc}`configuration`.

- Open the URL Uvicorn prints (default `http://127.0.0.1:8000`).
- **API:** `GET /api/users` (prefix configurable via {attr}`~fluxlit.config.FluxlitSettings.api_mount_path`).
- **OpenAPI:** `/api/docs`, `/api/openapi.json`.
- **Health:** `/api/healthz` (liveness; hidden from OpenAPI).
- **Readiness:** `/api/readyz` checks the Streamlit sidecar when running under `fluxlit dev` / `fluxlit run` (hidden from OpenAPI).

For structured per-request logs at the gateway (optional), set `FLUXLIT_ENABLE_GATEWAY_ACCESS_LOG=1` and read {doc}`observability`. The same page covers **JSON log lines** (`fluxlit.logging`), **correlation** (`X-Request-ID` end-to-end to Streamlit), and **SLO / alerting** sketches for `healthz` / `readyz`.

For local development, `fluxlit dev --reload --reload-scope=full` reloads the gateway and restarts Streamlit on changes; the default `--reload-scope=gateway` reloads FastAPI only. See {doc}`cli`.

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

## Next steps

| Topic | Doc |
|-------|-----|
| Reverse proxies, subpaths, OAuth base URL | {doc}`configuration` |
| Containers, probes, scaling | {doc}`deployment` |
| TLS, HSTS, `forwarded_allow_ips`, CSP notes | {doc}`production-tls` |
| Secrets in logs, secret stores, key rotation | {doc}`secrets` |
| Structured logs, JSON formatters, correlation, SLO notes, readiness details | {doc}`observability` |
| JWT / OIDC / Streamlit callers | {doc}`auth-recipes`, {doc}`security` |
| Markers, E2E, proxy smoke, `pip-audit` / SBOM CI | {doc}`testing` |
| Import errors, 503 readyz, API paths from Streamlit | {doc}`troubleshooting` |
