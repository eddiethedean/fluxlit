# Testing

```{note}
**App developers** can skip this page unless you contribute to FluxLit or run the full CI matrix locally. End users should start with {doc}`quickstart` and {doc}`troubleshooting`.
```

FluxLit’s tests fall into three bands: **fast** Pytest (default CI and local), **`slow`** subprocess checks, and **E2E** Playwright under `tests/e2e`. Docker-based **proxy smoke** exercises nginx-style routing. This page lists commands; {doc}`contributing` summarizes contributor workflow.

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

CI uploads `coverage.xml` as a workflow artifact for inspection (no enforced percentage gate yet).

## Security audit and SBOM (CI)

The **`security-audit`** workflow installs **`pip-audit`** and **`cyclonedx-bom`**, runs **`pip install -e ".[auth]"`**, then **`pip-audit`** and **`cyclonedx-py environment`** to produce **`cyclonedx-sbom.json`**. The SBOM is uploaded as workflow artifact **`cyclonedx-sbom`** (same dependency surface as the audit). See [SECURITY.md](https://github.com/eddiethedean/fluxlit/blob/main/SECURITY.md) in the repository for local commands and retention notes.

## Docker proxy smoke (integration)

From the repo root:

```bash
docker compose -f docker/proxy-deployment/docker-compose.yml up --build
./docker/proxy-deployment/smoke-test.sh
```

See [docker/proxy-deployment/README.md](../docker/proxy-deployment/README.md) for full-path, TLS, and `run-all-proxy-smokes.sh`.

## E2E

Default pytest config ignores `tests/e2e`; **pass the directory explicitly** so those tests are collected (see [`tests/conftest.py`](https://github.com/eddiethedean/fluxlit/blob/main/tests/conftest.py) for optional `pytest-playwright` registration).

```bash
python -m pip install -e ".[dev,e2e]"
python -m playwright install --with-deps chromium
python -m pytest tests/e2e -m e2e
```

The suite starts a real unified gateway (including Streamlit WebSocket traffic) and includes a **`FLUXLIT_ROOT_PATH`** / subpath regression (browser shell + `GET …/api/healthz` under the prefix).

## Readiness

With the unified runtime, `GET /api/readyz` returns **503** if the Streamlit upstream is unreachable or if `GET` on the upstream root does not return **2xx**. In bare FastAPI tests (no `FLUXLIT_STREAMLIT_UPSTREAM`), it returns **200** with `streamlit: not_configured`.

The runtime may expose the upstream URL via `FLUXLIT_STREAMLIT_UPSTREAM` and a companion state file so Uvicorn reload workers and Streamlit restarts stay consistent; tests cover file vs env precedence in `tests/test_runtime_upstream.py`.

## Fast suite highlights

The default CI/local command (`-m "not slow"`, no E2E) still exercises a broad slice of operations:

| Area | Examples |
|------|----------|
| Unified ASGI | `tests/test_asgi_unified.py` — lifespan + concurrent HTTP, httpx + `TestClient`, streaming bodies, sidecar failure |
| Readiness | `tests/test_health_probe.py`, `tests/test_gateway_readyz.py`, `tests/test_app.py` (`readyz`) |
| Gateway logging | `tests/test_gateway_access_log.py` |
| Gateway correlation + `httpx` wiring | `tests/test_gateway_correlation_integration.py` (threaded upstream, `build_gateway` + `proxy_settings`) |
| Gateway proxy edge cases | `tests/test_gateway_proxy_robust.py` (`_gateway_opts`, 502/413 paths, WebSocket connect kwargs) |
| JSON logging formatter | `tests/test_logging_json.py` |
| Upstream state | `tests/test_runtime_upstream.py` |
| Reload | `tests/test_streamlit_reload_watcher.py`, `tests/test_runtime_extra.py`, CLI tests for `--reload-scope` |
| Log redaction | `tests/test_logging_redact.py` |
| Doctor / auth env | `tests/test_cli.py` (`doctor`, PyJWT / JWT env) |

## Conventions

- Prefer **FluxLitTestClient** (see [test_fluxlit_testclient.py](https://github.com/eddiethedean/fluxlit/blob/main/tests/test_fluxlit_testclient.py)) when you need the real gateway stack.
- Use Streamlit **AppTest** for UI logic where versions allow.
- Gateway routing and proxy behavior: [test_gateway.py](https://github.com/eddiethedean/fluxlit/blob/main/tests/test_gateway.py), [test_gateway_unit.py](https://github.com/eddiethedean/fluxlit/blob/main/tests/test_gateway_unit.py), [test_gateway_forwarded.py](https://github.com/eddiethedean/fluxlit/blob/main/tests/test_gateway_forwarded.py), [test_gateway_http_upstream.py](https://github.com/eddiethedean/fluxlit/blob/main/tests/test_gateway_http_upstream.py), [test_gateway_correlation_integration.py](https://github.com/eddiethedean/fluxlit/blob/main/tests/test_gateway_correlation_integration.py), [test_gateway_proxy_robust.py](https://github.com/eddiethedean/fluxlit/blob/main/tests/test_gateway_proxy_robust.py).

For runtime or routing issues while developing, see {doc}`troubleshooting`.
