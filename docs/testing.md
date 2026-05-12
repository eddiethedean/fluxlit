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
python -m pytest
```

`FLUXLIT_TESTS=1` tells FluxLit's URL-session helpers to no-op by default, keeping
headless `AppTest` runs from depending on browser query-string continuity. Production
defaults are unchanged. Set `FLUXLIT_FORCE_URL_SESSION_IN_TESTS=1` only for tests
that explicitly cover URL-session behavior, or set `FLUXLIT_DISABLE_URL_SESSION=1`
to disable URL-session helpers in any environment.

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

FluxLit's Streamlit bootstrap uses `st.navigation(...)`, which `AppTest` can smoke-test
when the test starts on the default page. A minimal example lives in
`examples/multipage_apptest/`.

```python
from my_app import app
from fluxlit import FluxLitTestClient


def test_multipage_home(tmp_path):
    # Put your project root on sys.path, then point target at your FluxLit app.
    at = FluxLitTestClient(app).streamlit(target="my_app:app", extra_sys_path=tmp_path)
    assert at.title and at.title[0].value == "Home Page"
```

`FluxLitTestClient.streamlit()` sets `FLUXLIT_TESTS=1` during the run, so URL-session
helpers no-op by default unless you set `FLUXLIT_FORCE_URL_SESSION_IN_TESTS=1`.

Streamlit `AppTest` is still strongest when a test starts on one page and checks simple
widget state. It can be awkward for sidebar radios, fragment reruns, or tests that
switch pages after the first `.run()`. For now:

- Keep page-selection state behind app-level keys that tests can seed before `.run()`.
- Give important widgets stable `key=` values.
- Put table mutations and authorization in API/domain functions that can be tested
  without Streamlit.
- Add one `AppTest` smoke per important page, then use browser E2E for end-to-end
  navigation when the widget tree is unstable.

## Deep links and query parameters

Invite links and password-reset flows often land on the Streamlit shell with
`?token=...` (and optionally `?page=...`). Use {doc}`deep-links` for building
`page_url` / `for_page` links from FastAPI, {func}`fluxlit.query_params` in pages,
and `AppTest.query_params[...]` before `.run()` to assert prefilled widgets.
Repository tests live in `tests/test_deep_links.py`.

## FluxLitTestClient: subpaths, docs, query params, and `ApiClient`

### Path prefix (Workbench / Posit-style)

{class}`~fluxlit.testing.FluxLitTestClient` builds the same composite gateway as production.
When the browser URL includes a public mount (for example `/content/42/...`), use
:meth:`~fluxlit.testing.FluxLitTestClient.with_root_path` so :meth:`~fluxlit.testing.FluxLitTestClient.api_get`
emits ``{mount}{api_prefix}/…`` paths:

```python
from fluxlit import FluxLit, FluxLitTestClient


def make_app() -> FluxLit:
    app = FluxLit(title="Demo")

    @app.api.get("/widgets")
    def widgets():
        return [{"id": 1}]

    return app


def test_api_under_content_prefix():
    tc = FluxLitTestClient(make_app()).with_root_path("/content/42")
    res = tc.api_get("/widgets")
    assert res.status_code == 200
```

For a **single request** with a mount that differs from the client’s default, pass
``root_path=`` to :meth:`~fluxlit.testing.FluxLitTestClient.api_get` or
:meth:`~fluxlit.testing.FluxLitTestClient.api_post` (each call uses a matching
short-lived gateway). Prefer :meth:`~fluxlit.testing.FluxLitTestClient.with_root_path`
when most calls share one prefix.

If you use :attr:`~fluxlit.testing.FluxLitTestClient.api` directly, pass the **full**
public path (for example ``"/wb/api/healthz"``) when ``root_mount`` is non-empty.

### OpenAPI / Swagger smoke

:meth:`~fluxlit.testing.FluxLitTestClient.assert_docs_available` checks that
``GET …/openapi.json`` returns a valid OpenAPI document and that ``GET …/docs`` is
not missing (``200`` or common redirect codes). Optional ``root_path=`` matches the
``api_get`` / ``api_post`` helpers.

### Streamlit ``AppTest`` and query parameters

Pass ``query_params=`` to :meth:`~fluxlit.testing.FluxLitTestClient.streamlit` to seed
``AppTest.query_params`` before the first ``run()`` (same pattern as {doc}`deep-links`).
The bundled entrypoint (:mod:`fluxlit.streamlit.main`) calls
:func:`fluxlit.deep_links.match_nav_page` before :func:`streamlit.navigation`, so a
``page`` query value can open a registered FluxLit page (by **title**, **path**, or
**slug**).

### AppTest navigation helpers

- :meth:`~fluxlit.testing.FluxLitTestClient.assert_no_streamlit_exception` (and
  :func:`fluxlit.testing.apptest_assert_no_errors`) fail if ``AppTest`` collected
  ``st.exception`` or ``st.error``.
- :meth:`~fluxlit.testing.FluxLitTestClient.select_page` (and
  :func:`fluxlit.testing.apptest_select_page`) set ``at.query_params`` and ``run()``
  again with the same ``FLUXLIT_*`` patch as :meth:`~fluxlit.testing.FluxLitTestClient.streamlit`
  (pass ``target=`` and ``extra_sys_path=`` like the first call).

```python
from fluxlit import FluxLit, FluxLitTestClient

tc = FluxLitTestClient(FluxLit())
at = tc.streamlit(target="my_pkg.app:app", extra_sys_path=".", query_params={"page": "Admin"})
tc.assert_no_streamlit_exception(at)
at_home = tc.select_page(at, "Home", target="my_pkg.app:app", extra_sys_path=".")
```

### Bearer tokens: `with_bearer`, `for_fluxlit`, and the injected `client`

The page **injected `client`** has no `Authorization` header by default. For a token in
`st.session_state`, either chain :meth:`fluxlit.client.ApiClient.with_bearer` on that
client (same base URL and options) or construct :meth:`fluxlit.client.ApiClient.for_fluxlit`.
See {doc}`streamlit-api-client` for when to prefer each and for error-handling examples.

```python
from typing import Any

from fluxlit.client import ApiClient

# Option A: new client (common in snippets)
client = ApiClient.for_fluxlit(bearer_token=st.session_state["access_token"])
profile = client.get("/users/me").json()

# Option B: from the injected page client
def my_page(st: Any, client: ApiClient, /) -> None:
    with client.with_bearer(st.session_state["access_token"]) as api:
        profile = api.get("/users/me").json()
```

Exercise secured API routes with :class:`~fluxlit.testing.FluxLitTestClient` first
(fast, deterministic), then keep Streamlit ``AppTest`` assertions thin.

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

The **`coverage`** CI job runs the same measurement with **`--cov-fail-under=100`**
so merges cannot silently reduce the package coverage gate for `src/fluxlit`.
Reproduce the gate locally:

```bash
python -m pytest -n auto -m "not slow" \
  --cov=fluxlit --cov-report=term-missing --cov-fail-under=100
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

See [docker/proxy-deployment/README.md](../docker/proxy-deployment/README.md) for full-path, TLS, **`/apps/my-app`** strip-prefix (port **8083**), and `run-all-proxy-smokes.sh`.

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

## Type check (`ty`)

The **`ty-check`** workflow job runs **`ty check`** (pinned `ty` version; **`fluxlit[metrics]`** is installed so optional imports resolve). Run locally after `pip install ty` (and optional `pip install -e ".[metrics]"`) from the repo root.

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
| Workbench / Posit-style CLI | `tests/test_workbench.py`, `tests/test_runtime_extra.py` (`workbench_mode` banner), `tests/test_gateway.py` (prefixed mount root → Streamlit proxy) |
| JSON logging formatter | `tests/test_logging_json.py` |
| Upstream state | `tests/test_runtime_upstream.py` |
| Reload | `tests/test_streamlit_reload_watcher.py`, `tests/test_runtime_extra.py`, CLI tests for `--reload-scope` |
| Log redaction | `tests/test_logging_redact.py` |
| Doctor / auth env | `tests/test_cli.py`, `tests/test_cli_doctor_verbose.py` (`doctor`, `--verbose`, PyJWT / JWT env) |

## Conventions

- Shared fixtures live in [`tests/conftest.py`](https://github.com/eddiethedean/fluxlit/blob/main/tests/conftest.py): **`gateway_test_client_factory`** wraps `build_gateway` + `TestClient`; **`requires_streamlit_apptest`** centralizes the Streamlit ≥1.30 **AppTest** skip.
- Prefer **FluxLitTestClient** (see [test_fluxlit_testclient.py](https://github.com/eddiethedean/fluxlit/blob/main/tests/test_fluxlit_testclient.py)) when you need the real gateway stack.
- Use Streamlit **AppTest** for UI logic where versions allow (request the **`requires_streamlit_apptest`** fixture).
- Gateway routing and proxy behavior: [test_gateway.py](https://github.com/eddiethedean/fluxlit/blob/main/tests/test_gateway.py), [test_gateway_unit.py](https://github.com/eddiethedean/fluxlit/blob/main/tests/test_gateway_unit.py), [test_gateway_forwarded.py](https://github.com/eddiethedean/fluxlit/blob/main/tests/test_gateway_forwarded.py), [test_gateway_http_upstream.py](https://github.com/eddiethedean/fluxlit/blob/main/tests/test_gateway_http_upstream.py), [test_gateway_correlation_integration.py](https://github.com/eddiethedean/fluxlit/blob/main/tests/test_gateway_correlation_integration.py), [test_gateway_proxy_robust.py](https://github.com/eddiethedean/fluxlit/blob/main/tests/test_gateway_proxy_robust.py).

For runtime or routing issues while developing, see {doc}`troubleshooting`.
