# FluxLit

[![Documentation Status](https://readthedocs.org/projects/fluxlit/badge/?version=stable)](https://fluxlit.readthedocs.io/en/stable/?badge=stable)
[![PyPI version](https://img.shields.io/pypi/v/fluxlit.svg)](https://pypi.org/project/fluxlit/)
[![Python versions](https://img.shields.io/pypi/pyversions/fluxlit.svg)](https://pypi.org/project/fluxlit/)
[![CI](https://github.com/eddiethedean/fluxlit/actions/workflows/ci.yml/badge.svg)](https://github.com/eddiethedean/fluxlit/actions/workflows/ci.yml)
[![Release](https://github.com/eddiethedean/fluxlit/actions/workflows/release.yml/badge.svg)](https://github.com/eddiethedean/fluxlit/actions/workflows/release.yml)
[![License](https://img.shields.io/pypi/l/fluxlit)](LICENSE)

**FastAPI and Streamlit on one public port.** FluxLit gives you one `FluxLit` app object, a Uvicorn-powered ASGI gateway, and a managed Streamlit sidecar so your API and UI deploy together without hand-rolling a reverse proxy.

- **UI:** served from the app root on the URL Uvicorn prints, typically `http://127.0.0.1:8000`.
- **API:** mounted under `/api` by default, with OpenAPI at `/api/docs`.
- **Routing:** `/api/*` goes to FastAPI; everything else, including Streamlit WebSockets, is proxied to Streamlit.

**Docs:** [fluxlit.readthedocs.io](https://fluxlit.readthedocs.io/en/stable/) · **Security:** [SECURITY.md](SECURITY.md) · **Roadmap:** [ROADMAP.md](ROADMAP.md)

---

## Install

Python **3.10+**.

```bash
pip install fluxlit
```

Optional JWT / OIDC / BFF helpers: `pip install "fluxlit[auth]"` — see [Auth recipes](https://fluxlit.readthedocs.io/en/stable/auth-recipes.html).

For local development on FluxLit itself, clone the repository and run `pip install -e ".[dev]"`.

---

## Quick Start

```bash
fluxlit new my-app && cd my-app   # optional
```

`app.py`:

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

```bash
fluxlit dev    # default target app:app; or fluxlit dev your.module:app
```

Open the URL Uvicorn prints. The default gateway is `http://127.0.0.1:8000`; try `GET /api/users` or visit `/api/docs`.

In Streamlit, use paths like **`client.get("/users")`**, not `"/api/users"`. Secured routes need a client with credentials — [Auth recipes](https://fluxlit.readthedocs.io/en/stable/auth-recipes.html).

---

## What Ships

- **One app object:** `FluxLit` exposes `.api` for FastAPI and `@app.page(...)` for Streamlit pages.
- **Gateway runtime:** `fluxlit dev` and `fluxlit run` start Uvicorn plus a managed Streamlit subprocess.
- **Operational defaults:** health/readiness probes, request IDs, optional JSON logs, configurable gateway timeouts, body limits, concurrency, and graceful shutdown.
- **Deployment paths:** `fluxlit build`, Docker Compose, Kubernetes manifests, proxy smoke tests, and production TLS/proxy guidance.
- **Optional auth:** JWT validation, OIDC/BFF helpers, Streamlit-safe API clients, and security docs via `fluxlit[auth]`.

Start with the [Quick start](https://fluxlit.readthedocs.io/en/stable/quickstart.html), then see [Architecture](https://fluxlit.readthedocs.io/en/stable/architecture.html), [CLI](https://fluxlit.readthedocs.io/en/stable/cli.html), [Configuration](https://fluxlit.readthedocs.io/en/stable/configuration.html), and [Deployment](https://fluxlit.readthedocs.io/en/stable/deployment.html).

---

## Configuration

Precedence: **CLI → environment (`FLUXLIT_*`, `.env`) → `fluxlit.toml` / `[tool.fluxlit]` → defaults.**

```toml
# fluxlit.toml (optional)
target = "app:app"
gateway_host = "127.0.0.1"
gateway_port = 8000
```

Variable reference: [Configuration](https://fluxlit.readthedocs.io/en/stable/configuration.html).

**Gateway → Streamlit (optional env):** tune upstream HTTP timeouts, max proxied request body (returns **413** when exceeded), concurrent upstream HTTP cap, `httpx` connection limits, WebSocket open/ping/close timeouts, and optional frame size — see the **Gateway proxy** rows in [Configuration](https://fluxlit.readthedocs.io/en/stable/configuration.html#environment-variables). **`FLUXLIT_UVICORN_GRACEFUL_SHUTDOWN_TIMEOUT_S`** maps to Uvicorn’s graceful drain window when set (`fluxlit dev` / `fluxlit run`).

**Logs:** enable structured gateway lines with **`FLUXLIT_ENABLE_GATEWAY_ACCESS_LOG=1`**; for one JSON object per line in log aggregators, use **`fluxlit.logging.JsonLogFormatter`** (examples in [Observability](https://fluxlit.readthedocs.io/en/stable/observability.html)). Avoid logging secrets—see [Secrets](https://fluxlit.readthedocs.io/en/stable/secrets.html).

**TLS / edge:** behind a real proxy, tighten **`FLUXLIT_FORWARDED_ALLOW_IPS`**, validate **`X-Forwarded-Proto`**, and read [Production TLS](https://fluxlit.readthedocs.io/en/stable/production-tls.html) before enabling strict HSTS or CSP elsewhere.

---

## Production References

- [Deployment](https://fluxlit.readthedocs.io/en/stable/deployment.html): containers, probes, scaling, and Kubernetes graceful shutdown.
- [Observability](https://fluxlit.readthedocs.io/en/stable/observability.html): request correlation, JSON logs, Prometheus metrics, SLO notes, and runbooks.
- [Security architecture](https://fluxlit.readthedocs.io/en/stable/security.html), [Production TLS](https://fluxlit.readthedocs.io/en/stable/production-tls.html), and [Secrets](https://fluxlit.readthedocs.io/en/stable/secrets.html): auth boundaries, proxy trust, key rotation, and log hygiene.
- [`examples/kubernetes/`](examples/kubernetes/), [`examples/docker_compose/`](examples/docker_compose/), and [`examples/fullstack_demo/`](examples/fullstack_demo/): reference deployment and application patterns.

---

## Project Layout

```text
my_app/
├── app.py
├── fluxlit.toml
├── .env              # not committed
└── pkg/pages/        # optional: discover_pages(...)
```

---

## Contributors

```bash
pip install -e ".[dev]"
ruff check src tests && ruff format src tests
python -m pytest -n auto -m "not slow"
python -m mypy src/fluxlit
```

[Contributing](https://fluxlit.readthedocs.io/en/stable/contributing.html) · [Testing](https://fluxlit.readthedocs.io/en/stable/testing.html)

---

## Status

FluxLit is in the **0.x** line and actively hardening toward production use. Current releases include the unified gateway, page discovery, typed `ApiClient`, health/readiness probes, auth helpers, URL session utilities, gateway limits, structured logging helpers, Prometheus metrics, CI security audit/SBOM generation, Docker/Kubernetes examples, and deployment runbooks.

See the [changelog](https://fluxlit.readthedocs.io/en/stable/changelog.html), [support matrix](https://fluxlit.readthedocs.io/en/stable/support-matrix.html), and [roadmap](https://fluxlit.readthedocs.io/en/stable/roadmap.html) for release status and remaining work.

MIT — see [LICENSE](LICENSE).
