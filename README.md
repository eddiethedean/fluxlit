# FluxLit (`fluxlit`)

[![Documentation Status](https://readthedocs.org/projects/fluxlit/badge/?version=stable)](https://fluxlit.readthedocs.io/en/stable/?badge=stable)
[![PyPI version](https://img.shields.io/pypi/v/fluxlit.svg)](https://pypi.org/project/fluxlit/)
[![Python versions](https://img.shields.io/pypi/pyversions/fluxlit.svg)](https://pypi.org/project/fluxlit/)
[![CI](https://github.com/eddiethedean/fluxlit/actions/workflows/ci.yml/badge.svg)](https://github.com/eddiethedean/fluxlit/actions/workflows/ci.yml)
[![Release](https://github.com/eddiethedean/fluxlit/actions/workflows/release.yml/badge.svg)](https://github.com/eddiethedean/fluxlit/actions/workflows/release.yml)
[![License](https://img.shields.io/pypi/l/fluxlit)](https://github.com/eddiethedean/fluxlit/blob/main/LICENSE)

**One port** for **FastAPI** and **Streamlit**: a `FluxLit` app object, a Starlette **gateway** (Uvicorn), and Streamlit in a managed subprocess.

**Docs:** [fluxlit.readthedocs.io](https://fluxlit.readthedocs.io/en/stable/) · **Security policy & supply chain:** [SECURITY.md](SECURITY.md)

| | |
|--|--|
| [Quick start](https://fluxlit.readthedocs.io/en/stable/quickstart.html) | [Architecture](https://fluxlit.readthedocs.io/en/stable/architecture.html) · [CLI](https://fluxlit.readthedocs.io/en/stable/cli.html) · [Configuration](https://fluxlit.readthedocs.io/en/stable/configuration.html) |
| [Deployment](https://fluxlit.readthedocs.io/en/stable/deployment.html) · [Observability](https://fluxlit.readthedocs.io/en/stable/observability.html) · [Rate limiting](https://fluxlit.readthedocs.io/en/stable/rate-limiting.html) | [Production TLS & proxies](https://fluxlit.readthedocs.io/en/stable/production-tls.html) · [Secrets & key rotation](https://fluxlit.readthedocs.io/en/stable/secrets.html) |
| [Auth recipes](https://fluxlit.readthedocs.io/en/stable/auth-recipes.html) · [Auth migration](https://fluxlit.readthedocs.io/en/stable/migration-auth.html) · [Security architecture](https://fluxlit.readthedocs.io/en/stable/security.html) · [Troubleshooting](https://fluxlit.readthedocs.io/en/stable/troubleshooting.html) | **Ops:** correlation IDs, JSON logs, gateway limits, graceful shutdown — [Observability](https://fluxlit.readthedocs.io/en/stable/observability.html) · [Deployment](https://fluxlit.readthedocs.io/en/stable/deployment.html#kubernetes-graceful-shutdown) (Kubernetes) |
| [API reference](https://fluxlit.readthedocs.io/en/stable/api/index.html) | [Testing](https://fluxlit.readthedocs.io/en/stable/testing.html) · [Contributing](https://fluxlit.readthedocs.io/en/stable/contributing.html) · [Changelog](https://fluxlit.readthedocs.io/en/stable/changelog.html) · [Roadmap](https://fluxlit.readthedocs.io/en/stable/roadmap.html) |

**Kubernetes:** reference `Deployment` + `Service` in [`examples/kubernetes/`](examples/kubernetes/) (probes, graceful shutdown, `preStop`). **Runbooks:** [Runbooks](https://fluxlit.readthedocs.io/en/stable/runbooks.html). **Support matrix:** [support-matrix](https://fluxlit.readthedocs.io/en/stable/support-matrix.html).

Longer product context: [PLAN.md](PLAN.md).

---

## Install

Python **3.10+**.

```bash
pip install fluxlit
```

Optional JWT / OIDC / BFF helpers: `pip install "fluxlit[auth]"` — see [Auth recipes](https://fluxlit.readthedocs.io/en/stable/auth-recipes.html).

**Hack on FluxLit:** `git clone` this repo, then `pip install -e ".[dev]"`.

---

## Quick start

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

- **UI:** app root on the URL Uvicorn prints (default port **8000**).
- **API:** under **`/api`** (e.g. `GET /api/users`). OpenAPI: **`/api/docs`**.
- **Health / readiness:** **`/api/healthz`**, **`/api/readyz`** (see [Deployment](https://fluxlit.readthedocs.io/en/stable/deployment.html)).

In Streamlit, use paths like **`client.get("/users")`**, not `"/api/users"`. Secured routes need a client with credentials — [Auth recipes](https://fluxlit.readthedocs.io/en/stable/auth-recipes.html).

**Routing:** `/api/*` → FastAPI (prefix stripped inside the app); **everything else** → Streamlit (HTTP + WebSocket). Details: [Architecture](https://fluxlit.readthedocs.io/en/stable/architecture.html).

---

## CLI (summary)

| Command | Role |
|---------|------|
| `fluxlit dev` | Dev server; optional `--reload` and `--reload-scope` (`gateway` or `full`) |
| `fluxlit run` | Same stack, no reloader (typical in containers) |
| `fluxlit doctor` | Import, bind, env sanity checks |
| `fluxlit build` | Emit starter `Dockerfile` + `.dockerignore` (digest-pinned base image, non-root `appuser`; add your own lockfile for production deps) |
| `fluxlit new` | Minimal scaffold |

Proxy / subpath: **`FLUXLIT_ROOT_PATH`**, **`FLUXLIT_TRUST_PROXY`**. Full flags and PID file: [CLI](https://fluxlit.readthedocs.io/en/stable/cli.html).

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

**Logs:** enable structured gateway lines with **`FLUXLIT_ENABLE_GATEWAY_ACCESS_LOG=1`**; for one JSON object per line in log aggregators, use **`fluxlit.logging_json.JsonLogFormatter`** (examples in [Observability](https://fluxlit.readthedocs.io/en/stable/observability.html)). Avoid logging secrets—see [Secrets](https://fluxlit.readthedocs.io/en/stable/secrets.html).

**TLS / edge:** behind a real proxy, tighten **`FLUXLIT_FORWARDED_ALLOW_IPS`**, validate **`X-Forwarded-Proto`**, and read [Production TLS](https://fluxlit.readthedocs.io/en/stable/production-tls.html) before enabling strict HSTS or CSP elsewhere.

---

## Project layout (sketch)

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

Shipped: unified gateway, `@app.page` / `discover_pages`, `fluxlit.toml`, typed `ApiClient`, health/readiness probes, optional gateway access logs, **upstream `X-Request-ID` correlation** (HTTP + WebSocket to Streamlit), **configurable gateway timeouts / body limits / concurrency and `httpx` pool limits**, **JSON log formatter**, **Uvicorn graceful shutdown** for orchestrated deploys, dev reload scopes, **`fluxlit[auth]`**, CI (proxy smoke, Playwright e2e, **`pip-audit`** + **CycloneDX SBOM** artifact on `.[auth]` per [SECURITY.md](SECURITY.md)). **Container templates:** `fluxlit build`, `examples/docker_compose/`, and `docker/proxy-deployment/` use digest-pinned **Python slim** and **non-root** runtime where applicable; Compose example includes a **`pip-compile`** lockfile. **Docs:** [Production TLS](https://fluxlit.readthedocs.io/en/stable/production-tls.html), [Secrets](https://fluxlit.readthedocs.io/en/stable/secrets.html). **Roadmap:** [Read the Docs](https://fluxlit.readthedocs.io/en/stable/roadmap.html).

MIT — see [LICENSE](LICENSE).
