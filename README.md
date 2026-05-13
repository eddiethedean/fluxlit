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

**Docs:** [fluxlit.readthedocs.io](https://fluxlit.readthedocs.io/en/stable/) · **Security:** [SECURITY.md](SECURITY.md) · **Roadmap:** [ROADMAP.md](ROADMAP.md) · **Changelog:** [CHANGELOG.md](CHANGELOG.md) (release **0.13.0**)

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
from typing import Any

from fluxlit import FluxLit
from fluxlit.client import ApiClient

app = FluxLit(title="Admin Portal")

@app.api.get("/users")
def users():
    return [{"name": "Ada"}]

@app.page("/")
def home(st: Any, client: ApiClient) -> None:
    st.title("Dashboard")
    st.write(client.get("/users").json())
```

Optional typed-page patterns (**0.9+**): `Depends`, `parse_query_params`, `PageMeta`, manifests — see [Streamlit pages: typing](https://fluxlit.readthedocs.io/en/stable/streamlit-pages-typing.html) and [`examples/roadmap_09/`](examples/roadmap_09/). **0.10** adds async `Depends` when an asyncio loop is already running, an **opt-in** allowlist that **merges** extra browser header names onto the gateway → Streamlit HTTP hop (see [Security](https://fluxlit.readthedocs.io/en/stable/security.html) for baseline vs allowlist behavior), and a [cookbook](https://fluxlit.readthedocs.io/en/stable/cookbook.html) of copy-paste recipes.

```bash
fluxlit dev    # default target app:app; or fluxlit dev your.module:app
```

Open the URL Uvicorn prints. The default gateway is `http://127.0.0.1:8000`; try `GET /api/users` or visit `/api/docs`.

In Streamlit, use paths like **`client.get("/users")`**, not `"/api/users"`. Secured routes need a client with credentials — [Auth recipes](https://fluxlit.readthedocs.io/en/stable/auth-recipes.html).

---

## What Ships

- **One app object:** `FluxLit` exposes `.api` for FastAPI and `@app.page(...)` for Streamlit pages (optional **0.9+** typing: `Depends`, `Annotated`, query/session models, `PageMeta`, `fluxlit pages manifest`; **0.10** improves async `Depends` under Streamlit’s execution model and optional gateway header allowlist merging on the HTTP hop to Streamlit — see [Configuration](https://fluxlit.readthedocs.io/en/stable/configuration.html) and [Security](https://fluxlit.readthedocs.io/en/stable/security.html)).
- **Diagnostics, CI gates, and scaling guard (0.11–0.13):** `fluxlit config` / `fluxlit doctor` warn when the gateway header allowlist names credential-style headers that are never forwarded, when `trust_proxy` is on with an unlimited proxied upload body cap, and when **`fluxlit doctor --verbose`** includes **`gateway_proxy`** limits in JSON. **`fluxlit doctor --strict`** (from **0.12**, expanded in **0.13**) turns additional proxy, URL, timeout, and CORS/security mismatches into **FAIL** for production-style CI; optional **`FLUXLIT_STRICT_STARTUP`** fails settings construction for the same class of issues. Unified ASGI **lifespan** fails fast if Uvicorn runs with **`workers` > 1** (override only with **`FLUXLIT_ALLOW_UNIFIED_UVICORN_MULTIWORKER=1`** — unsupported); see [Deployment](https://fluxlit.readthedocs.io/en/stable/deployment.html) and [CLI](https://fluxlit.readthedocs.io/en/stable/cli.html).
- **Gateway runtime:** `fluxlit dev` and `fluxlit run` start Uvicorn plus a managed Streamlit subprocess.
- **Operational defaults:** health/readiness probes, request IDs, optional JSON logs, configurable gateway timeouts, body limits, concurrency, and graceful shutdown.
- **Quality gate:** package tests enforce **100% line coverage** for `src/fluxlit` in CI; a single internal import guard in the test helpers uses `# pragma: no cover` for an unreachable defensive branch.
- **Deployment paths:** `fluxlit build`, Docker Compose, Kubernetes manifests (including optional **PDB** and **session affinity** examples), proxy smoke tests (nginx, Traefik, **Caddy** strip-prefix, full-path, root, HTTPS, and **`/apps/my-app`**), multi-replica checklists in the docs, and production TLS/proxy guidance.
- **Optional auth:** JWT validation, OIDC/BFF helpers, Streamlit-safe API clients, and security docs via `fluxlit[auth]`.
- **Testing and diagnostics:** `FluxLitTestClient`, `streamlit_main_path()`, AppTest recipes (including **`apptest_select_page`** / **`apptest_assert_no_errors`** for multipage and query params), URL-session test-mode defaults, optional **`?page=`** deep links before `st.navigation` with multipage apps, and expanded `fluxlit doctor` / **`fluxlit config`** diagnostics (readiness route, WebSocket expectations, gateway timeouts, async deps, optional header-forwarding hints, rejected allowlist names, **`gateway_proxy`** limits in **`--verbose`** JSON, plus **`doctor --strict`** for CI). Repository **`scripts/soak_*.sh`** and [Testing](https://fluxlit.readthedocs.io/en/stable/testing.html) document short readiness soaks. Gateway Prometheus histogram observe failures log at **DEBUG** on `fluxlit.gateway` without failing the request.

Start with the [Quick start](https://fluxlit.readthedocs.io/en/stable/quickstart.html), then see [Architecture](https://fluxlit.readthedocs.io/en/stable/architecture.html), [CLI](https://fluxlit.readthedocs.io/en/stable/cli.html), [Configuration](https://fluxlit.readthedocs.io/en/stable/configuration.html), [Deployment](https://fluxlit.readthedocs.io/en/stable/deployment.html), and the [Cookbook](https://fluxlit.readthedocs.io/en/stable/cookbook.html).

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

**Gateway → Streamlit (optional env):** tune upstream HTTP timeouts, max proxied request body (returns **413** when exceeded), concurrent upstream HTTP cap, `httpx` connection limits, WebSocket open/ping/close timeouts, and optional frame size — see the **Gateway proxy** rows in [Configuration](https://fluxlit.readthedocs.io/en/stable/configuration.html#environment-variables). **`FLUXLIT_GATEWAY_FORWARD_CLIENT_HEADERS_TO_STREAMLIT`** (JSON list, **default empty**) **merges** additional header names from the raw browser request onto the HTTP hop; the baseline proxy already forwards most non–hop-by-hop client headers (see [Security](https://fluxlit.readthedocs.io/en/stable/security.html)). **`FLUXLIT_ALLOW_UNIFIED_UVICORN_MULTIWORKER`** skips the unified-stack check that rejects Uvicorn **`workers` > 1** (default off; only if you accept an unsupported layout). **`FLUXLIT_UVICORN_GRACEFUL_SHUTDOWN_TIMEOUT_S`** maps to Uvicorn’s graceful drain window when set (`fluxlit dev` / `fluxlit run`).

**Logs:** enable structured gateway lines with **`FLUXLIT_ENABLE_GATEWAY_ACCESS_LOG=1`**; for one JSON object per line in log aggregators, use **`fluxlit.logging.JsonLogFormatter`** (examples in [Observability](https://fluxlit.readthedocs.io/en/stable/observability.html)). Avoid logging secrets—see [Secrets](https://fluxlit.readthedocs.io/en/stable/secrets.html).

**TLS / edge:** behind a real proxy, tighten **`FLUXLIT_FORWARDED_ALLOW_IPS`**, validate **`X-Forwarded-Proto`**, and read [Production TLS](https://fluxlit.readthedocs.io/en/stable/production-tls.html) before enabling strict HSTS or CSP elsewhere.

---

## Production References

- [Deployment](https://fluxlit.readthedocs.io/en/stable/deployment.html): containers, probes, scaling, Kubernetes graceful shutdown, and a reverse-proxy compatibility matrix (nginx, Traefik, Caddy).
- [Cookbook](https://fluxlit.readthedocs.io/en/stable/cookbook.html): copy-paste patterns (headers, multipage, tests, pins).
- [Observability](https://fluxlit.readthedocs.io/en/stable/observability.html): request correlation, JSON logs, Prometheus metrics, SLO notes, and runbooks.
- [Security architecture](https://fluxlit.readthedocs.io/en/stable/security.html), [Production TLS](https://fluxlit.readthedocs.io/en/stable/production-tls.html), and [Secrets](https://fluxlit.readthedocs.io/en/stable/secrets.html): auth boundaries, proxy trust, key rotation, and log hygiene.
- [Support matrix](https://fluxlit.readthedocs.io/en/stable/support-matrix.html): Python and dependency versions tested in CI, pinning guidance (`uv` / `pip-tools` / constraints), **stability charter** tables (metrics, manifests, logs, experimental settings), and upgrade notes for `FluxLitTestClient` and Streamlit `AppTest`.
- [`examples/kubernetes/`](examples/kubernetes/), [`examples/docker_compose/`](examples/docker_compose/), [`examples/path_prefixed_proxy/`](examples/path_prefixed_proxy/), [`examples/multipage_apptest/`](examples/multipage_apptest/), [`examples/roadmap_09/`](examples/roadmap_09/) (typed Streamlit pages), and [`examples/fullstack_demo/`](examples/fullstack_demo/): reference deployment and application patterns. Runnable nginx, Traefik, and Caddy + FluxLit smoke stacks (including **`/apps/my-app`**) live under [`docker/proxy-deployment/`](docker/proxy-deployment/).

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
python -m ruff format && python -m ruff check
python -m mypy src/fluxlit
ty check
python -m pytest -n auto --cov=fluxlit --cov-report=term-missing --cov-fail-under=100
```

[Contributing](https://fluxlit.readthedocs.io/en/stable/contributing.html) · [Testing](https://fluxlit.readthedocs.io/en/stable/testing.html)

---

## Status

FluxLit is in the **0.x** line and actively hardening toward production use. Current releases include the unified gateway, page discovery, typed `ApiClient`, optional Streamlit page typing (`Depends`, query models, `PageMeta`, manifests), **0.10**-era async `Depends` handling when an event loop is already active, default-empty **allowlist merge** for extra gateway → Streamlit HTTP headers (see Security for wire vs allowlist semantics), **0.11**-era **`fluxlit config`** / **`fluxlit doctor`** warnings for mis-tuned header allowlists and `trust_proxy` with unlimited proxied upload size, **0.12**-era **`fluxlit doctor --strict`** and operator-facing **stability tables** (metrics, manifests, logs, experimental settings) in the [support matrix](https://fluxlit.readthedocs.io/en/stable/support-matrix.html) and [observability](https://fluxlit.readthedocs.io/en/stable/observability.html) docs, plus multi-replica guidance and soak/runbook alignment, **0.13**-era **metrics soak** tooling and **`FLUXLIT_STRICT_STARTUP`**, and upstream tracing hook coverage in observability docs. A **lifespan guard** still fails startup when `uvicorn … --workers N` is used on the unified `FluxLit` ASGI app unless explicitly overridden. Also: health/readiness probes, auth helpers, URL session utilities, AppTest-friendly navigation and query-param helpers, expanded doctor signals, gateway limits, structured logging helpers, Prometheus metrics, CI security audit/SBOM generation, Docker/Kubernetes examples, path-prefixed reverse-proxy documentation and multi-engine smoke coverage (including Traefik in the proxy matrix), deployment runbooks, a [cookbook](https://fluxlit.readthedocs.io/en/stable/cookbook.html), and a 100% package line-coverage gate for `src/fluxlit` in CI.

See the [changelog](https://fluxlit.readthedocs.io/en/stable/changelog.html), [support matrix](https://fluxlit.readthedocs.io/en/stable/support-matrix.html), and [roadmap](https://fluxlit.readthedocs.io/en/stable/roadmap.html) for release status and remaining work.

MIT — see [LICENSE](LICENSE).
