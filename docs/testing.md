# Testing

This page covers two audiences:

- **App developers** writing tests for a FluxLit app with Pytest, `FluxLitTestClient`,
  `ApiClient`, and Streamlit `AppTest`.
- **FluxLit contributors** running the repository CI matrix locally.

FluxLit’s own tests fall into three bands: **fast** Pytest (default CI and local),
**`slow`** subprocess checks, and **E2E** Playwright under `tests/e2e`. Docker-based
**proxy smoke** exercises nginx-style routing. {doc}`contributing` summarizes
contributor workflow.

## Quick start

```bash
python -m pip install -e ".[dev]"
python -m pytest -n auto -m "not slow"
```

That matches the main **`test`** CI job (fast suite, no browser tests, no `slow` marker). The project’s pytest config **ignores `tests/e2e` by default** (see `addopts` in `pyproject.toml`), so a plain `python -m pytest` from the repo root collects the fast tree without Playwright. Browser E2E still runs when you **pass the directory explicitly** (see [E2E](#e2e)). A plain `pytest` still runs **`slow`** tests unless you add `-m "not slow"`.

Parallel without the `slow` filter:

```bash
python -m pytest -n auto
```

## Pytest recipe for apps

A minimal app test can exercise the real FluxLit gateway without opening sockets:

```python
# tests/test_app.py
from fluxlit import FluxLit, FluxLitTestClient


def make_app() -> FluxLit:
    app = FluxLit(title="Tested App")

    @app.api.get("/users")
    def users():
        return [{"name": "Ada"}]

    return app


def test_api_users():
    client = FluxLitTestClient(make_app())
    response = client.api_get("/users")
    assert response.status_code == 200
    assert response.json() == [{"name": "Ada"}]
```

Use `FluxLitTestClient` for API and OpenAPI assertions because it routes through the
same gateway prefix rules as production (`/api` by default). Use plain FastAPI
`TestClient(app.api)` only when you intentionally want to bypass the gateway.

Recommended test environment for Streamlit UI tests:

```bash
export FLUXLIT_TESTS=1
export FLUXLIT_DISABLE_URL_SESSION=1
python -m pytest
```

`FLUXLIT_TESTS=1` is a convention for test-only branches in app code. Explicitly
setting `FLUXLIT_DISABLE_URL_SESSION=1` keeps headless `AppTest` runs from depending
on browser query-string continuity; production defaults are unchanged.

## What to test where

- **API logic and authorization:** test through `FluxLitTestClient.api_get(...)`,
  `api_post(...)`, or `openapi()`. These tests are fast and deterministic.
- **Streamlit page smoke:** use `FluxLitTestClient.streamlit(...)` or
  `AppTest.from_file(str(streamlit_main_path()))` to assert that pages render expected
  titles, text, and simple widgets.
- **`ApiClient` calls from Streamlit:** prefer testing API endpoints directly, then keep
  Streamlit tests thin. If you need to intercept calls, monkeypatch
  `fluxlit.client.ApiClient.request` at the app boundary.
- **Admin tables, `st.data_editor`, selection, and dynamic `key=` remounts:** keep
  business rules and persistence in API/domain tests. Use Streamlit `AppTest` for a
  small render smoke, and use browser E2E for flows that depend on rich frontend
  interactions.
- **Multipage navigation:** seed session state or call page functions through stable
  app-level helpers where possible. See the multipage notes below for current
  limitations.

## AppTest entrypoint

When app tests need Streamlit's `AppTest.from_file(...)`, use FluxLit's public helper
instead of constructing a path from `fluxlit.__file__`:

```python
from streamlit.testing.v1 import AppTest

from fluxlit import streamlit_main_path


def test_home_page(monkeypatch):
    monkeypatch.setenv("FLUXLIT_APP", "app:app")
    at = AppTest.from_file(str(streamlit_main_path())).run()
    assert at.title
```

`streamlit_main_path()` points at the bundled Streamlit bootstrap that `fluxlit dev`
and `FluxLitTestClient.streamlit()` use, while keeping tests independent of FluxLit's
internal package layout.

## Multipage and menu-heavy UIs

Streamlit `AppTest` is strongest when a test starts on one page and checks simple
widget state. It can be awkward for sidebar radios, `st.navigation`, fragment reruns,
or tests that switch pages after the first `.run()`. For now:

- Keep page-selection state behind app-level keys that tests can seed before `.run()`.
- Give important widgets stable `key=` values.
- Put table mutations and authorization in API/domain functions that can be tested
  without Streamlit.
- Add one `AppTest` smoke per important page, then use browser E2E for end-to-end
  navigation when the widget tree is unstable.

## Markers

| Marker | Meaning |
|--------|---------|
| `e2e` | Playwright browser tests — needs `pip install -e ".[dev,e2e]"` and `python -m playwright install --with-deps chromium` |
| `slow` | Subprocess / long-running — excluded from the default PR matrix; run with `pytest -m slow` or rely on the `slow-tests` CI job |

Run everything except slow:

```bash
python -m pytest -n auto -m "not slow"
```

## Coverage

Local HTML + terminal summary (same as the `coverage` CI job, without XML):

```bash
python -m pytest -n auto \
  --cov=fluxlit --cov-report=term-missing --cov-report=html
open htmlcov/index.html
```

The **`coverage`** CI job runs the same measurement with **`--cov-fail-under=80`** so merges cannot silently collapse overall line coverage (current baseline is ~85%; the floor leaves headroom for platform noise). Reproduce the gate locally:

```bash
python -m pytest -n auto -m "not slow" \
  --cov=fluxlit --cov-report=term-missing --cov-fail-under=80
```

CI uploads `coverage.xml` as a workflow artifact. Third-party PR comment bots (Codecov, etc.) remain optional if you want diff-based coverage later.

## Security audit and SBOM (CI)

The **`security-audit`** workflow installs **`pip-audit`** and **`cyclonedx-bom`**, runs **`pip install -e ".[auth]"`**, then **`pip-audit`** and **`cyclonedx-py environment`** to produce **`cyclonedx-sbom.json`**. The SBOM is uploaded as workflow artifact **`cyclonedx-sbom`** (same dependency surface as the audit). See [SECURITY.md](https://github.com/eddiethedean/fluxlit/blob/main/SECURITY.md) in the repository for local commands and retention notes.

## Docker proxy smoke (integration)

From the repo root:

```bash
docker compose -f docker/proxy-deployment/docker-compose.yml up --build
./docker/proxy-deployment/smoke-test.sh
```

See [docker/proxy-deployment/README.md](../docker/proxy-deployment/README.md) for full-path, TLS, and `run-all-proxy-smokes.sh`.

## OpenAPI contract

`tests/test_openapi_contract.py` compares the **default** `FluxLit` OpenAPI document (empty `paths`, fixed `servers`) to **`tests/fixtures/openapi_contract_minimal.json`**. If you add a route to the default FastAPI surface without opting out of the schema, CI fails until you update the fixture intentionally.

## Chaos and failure injection

- **`tests/test_asgi_unified.py`** — lifespan, concurrent and **serial burst** `healthz`, streaming request bodies, **sidecar exit** → 503, chunked POST to API.
- **`tests/test_gateway_proxy_robust.py`** — upstream **connect** / **read timeout** → **502**, body limits, WebSocket edge kwargs.

## Canonical smoke app

Release, proxy, E2E, and local load checks share the tiny app in
`examples/smoke_app/`. Its public contract is intentionally small:

- `GET /api/healthz` returns `{"status": "ok"}`.
- `GET /api/smoke` includes marker `fluxlit_smoke_ok`.
- The Streamlit home page renders `FluxLit Smoke` and `fluxlit_smoke_ok`.

Run it from the repository root with:

```bash
./scripts/run_smoke_app.sh
```

## Soak / load (local)

With the canonical smoke app listening on port 8000:

```bash
chmod +x scripts/soak_http.sh
COUNT=500 BASE_URL=http://127.0.0.1:8000 PATH_SUFFIX=/api/smoke ./scripts/soak_http.sh
```

Set `OUTPUT_FORMAT=json` or `OUTPUT_FORMAT=markdown` for a machine-readable or
report-friendly summary with approximate p50/p95/p99 latency in milliseconds.
Adjust `PATH_SUFFIX` (default `/api/healthz`) or `COUNT` for longer runs. Watch
gateway CPU and logs; pair with {doc}`observability` if you enable access logs.

## Chaos checks (local)

The sidecar-failure check starts the canonical smoke app, kills the Streamlit child
process, and verifies that the gateway exits instead of serving a broken UI:

```bash
./scripts/chaos_streamlit_kill.sh
```

Additional local/manual checks:

```bash
./scripts/chaos_slow_upstream.sh
./scripts/chaos_oversized_body.sh
./scripts/chaos_dropped_websocket.sh
./scripts/chaos_graceful_shutdown.sh
```

Keep chaos scripts local/manual unless they are explicitly marked slow in CI; they
intentionally manipulate subprocesses.

The **[`.github/workflows/soak-scheduled.yml`](https://github.com/eddiethedean/fluxlit/blob/main/.github/workflows/soak-scheduled.yml)** workflow runs **weekly** (and **`workflow_dispatch`**) against `python -m http.server` to ensure `scripts/soak_http.sh` still works; it does **not** start FluxLit.

## Upgrade matrix (latest deps)

The **[`.github/workflows/upgrade-smoke.yml`](https://github.com/eddiethedean/fluxlit/blob/main/.github/workflows/upgrade-smoke.yml)** workflow runs **weekly** (Mondays) and **`workflow_dispatch`**: it installs **latest** `streamlit`, `fastapi`, and `starlette` from PyPI, then runs the fast pytest suite. It uses **`continue-on-error: true`** so failures surface as signals for maintainers without blocking merges. Supported version ranges for releases are documented in {doc}`support-matrix`.

## E2E

Default pytest config ignores `tests/e2e`; **pass the directory explicitly** so those tests are collected (see [`tests/conftest.py`](https://github.com/eddiethedean/fluxlit/blob/main/tests/conftest.py) for optional `pytest-playwright` registration).

```bash
python -m pip install -e ".[dev,e2e]"
python -m playwright install --with-deps chromium
python -m pytest tests/e2e -m e2e --tracing=retain-on-failure
```

The suite starts a real unified gateway (including Streamlit WebSocket traffic) and includes a **`FLUXLIT_ROOT_PATH`** / subpath regression (browser shell + `GET …/api/healthz` under the prefix).

On **CI failures**, the workflow uploads **`test-results/`** as artifact **`playwright-traces`** for inspection.

## Optional type check (`ty`)

CI runs **[`ty check`](https://docs.astral.sh/ty/)** in a **`ty-check`** job with **`continue-on-error: true`** (installs **`fluxlit[metrics]`** so optional imports resolve). Run locally after `pip install ty` (and optional `pip install -e ".[metrics]"`) from the repo root.

## Readiness

With the unified runtime, `GET /api/readyz` returns **503** if the Streamlit upstream is unreachable or if `GET` on the upstream root does not return **2xx**. In bare FastAPI tests (no `FLUXLIT_STREAMLIT_UPSTREAM`), it returns **200** with `streamlit: not_configured`.

The runtime may expose the upstream URL via `FLUXLIT_STREAMLIT_UPSTREAM` and a companion state file so Uvicorn reload workers and Streamlit restarts stay consistent; tests cover file vs env precedence in `tests/test_runtime_upstream.py`.

## Fast suite highlights

The default CI/local command (`-m "not slow"`, no E2E) still exercises a broad slice of operations:

| Area | Examples |
|------|----------|
| Unified ASGI | `tests/test_asgi_unified.py` — lifespan + concurrent/serial HTTP, httpx + `TestClient`, streaming bodies, sidecar failure |
| OpenAPI contract | `tests/test_openapi_contract.py` — default app schema vs fixture |
| URL session (no cookies) | `tests/test_url_session.py`, `tests/test_url_session_apptest.py`, `tests/test_url_session_contract.py` |
| Gateway Prometheus | `tests/test_gateway_unit.py` (requires `prometheus_client` / `fluxlit[metrics]`) |
| Readiness | `tests/test_health_probe.py`, `tests/test_gateway_readyz.py`, `tests/test_app.py` (`readyz`) |
| Gateway logging | `tests/test_gateway_access_log.py` |
| Gateway correlation + `httpx` wiring | `tests/test_gateway_correlation_integration.py` (threaded upstream, `build_gateway` + `proxy_settings`) |
| Gateway proxy edge cases | `tests/test_gateway_proxy_robust.py` (`_gateway_opts`, 502/413 paths, WebSocket connect kwargs) |
| Gateway WebSocket | `tests/test_gateway_ws_echo.py` — echo proxy; **`slow`** repeated connect/disconnect stress |
| JSON logging formatter | `tests/test_logging_json.py` |
| Upstream state | `tests/test_runtime_upstream.py` |
| Reload | `tests/test_streamlit_reload_watcher.py`, `tests/test_runtime_extra.py`, CLI tests for `--reload-scope` |
| Log redaction | `tests/test_logging_redact.py` |
| Doctor / auth env | `tests/test_cli.py` (`doctor`, PyJWT / JWT env) |

## Conventions

- Shared fixtures live in [`tests/conftest.py`](https://github.com/eddiethedean/fluxlit/blob/main/tests/conftest.py): **`gateway_test_client_factory`** wraps `build_gateway` + `TestClient`; **`requires_streamlit_apptest`** centralizes the Streamlit ≥1.30 **AppTest** skip.
- Prefer **FluxLitTestClient** (see [test_fluxlit_testclient.py](https://github.com/eddiethedean/fluxlit/blob/main/tests/test_fluxlit_testclient.py)) when you need the real gateway stack.
- Use Streamlit **AppTest** for UI logic where versions allow (request the **`requires_streamlit_apptest`** fixture).
- Gateway routing and proxy behavior: [test_gateway.py](https://github.com/eddiethedean/fluxlit/blob/main/tests/test_gateway.py), [test_gateway_unit.py](https://github.com/eddiethedean/fluxlit/blob/main/tests/test_gateway_unit.py), [test_gateway_forwarded.py](https://github.com/eddiethedean/fluxlit/blob/main/tests/test_gateway_forwarded.py), [test_gateway_http_upstream.py](https://github.com/eddiethedean/fluxlit/blob/main/tests/test_gateway_http_upstream.py), [test_gateway_correlation_integration.py](https://github.com/eddiethedean/fluxlit/blob/main/tests/test_gateway_correlation_integration.py), [test_gateway_proxy_robust.py](https://github.com/eddiethedean/fluxlit/blob/main/tests/test_gateway_proxy_robust.py).

For runtime or routing issues while developing, see {doc}`troubleshooting`.
