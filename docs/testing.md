# Testing

## Quick start

```bash
python -m pip install -e ".[dev]"
python -m pytest -n auto --ignore=tests/e2e -m "not slow"
```

That matches the main **`test`** CI job (fast suite, no browser tests, no `slow` marker). A plain `python -m pytest` from the repo root also collects **`tests/e2e`** (needs `.[e2e]` + Playwright browsers) and runs **`slow`** tests — use the command above for day-to-day work.

Parallel without the `slow` filter (still ignores E2E):

```bash
python -m pytest -n auto --ignore=tests/e2e
```

## Markers

| Marker | Meaning |
|--------|---------|
| `e2e` | Playwright browser tests — needs `pip install -e ".[dev,e2e]"` and `python -m playwright install --with-deps chromium` |
| `slow` | Subprocess / long-running — excluded from the default PR matrix; run with `pytest -m slow` or rely on the `slow-tests` CI job |

Run everything except slow:

```bash
python -m pytest -n auto --ignore=tests/e2e -m "not slow"
```

## Coverage

Local HTML + terminal summary (same as the `coverage` CI job, without XML):

```bash
python -m pytest -n auto --ignore=tests/e2e \
  --cov=fluxlit --cov-report=term-missing --cov-report=html
open htmlcov/index.html
```

CI uploads `coverage.xml` as a workflow artifact for inspection (no enforced percentage gate yet).

## Docker proxy smoke (integration)

From the repo root:

```bash
docker compose -f docker/proxy-deployment/docker-compose.yml up --build
./docker/proxy-deployment/smoke-test.sh
```

See [docker/proxy-deployment/README.md](../docker/proxy-deployment/README.md) for full-path, TLS, and `run-all-proxy-smokes.sh`.

## E2E

```bash
python -m pip install -e ".[dev,e2e]"
python -m playwright install --with-deps chromium
python -m pytest tests/e2e -m e2e
```

The suite starts a real unified gateway (including Streamlit WebSocket traffic) and includes a **`FLUXLIT_ROOT_PATH`** / subpath regression (browser shell + `GET …/api/healthz` under the prefix).

## Conventions

- Prefer **FluxLitTestClient** (see [test_fluxlit_testclient.py](https://github.com/eddiethedean/fluxlit/blob/main/tests/test_fluxlit_testclient.py)) when you need the real gateway stack.
- Use Streamlit **AppTest** for UI logic where versions allow.
- Gateway routing and proxy behavior: [test_gateway.py](https://github.com/eddiethedean/fluxlit/blob/main/tests/test_gateway.py), [test_gateway_unit.py](https://github.com/eddiethedean/fluxlit/blob/main/tests/test_gateway_unit.py), [test_gateway_proxy_*.py](https://github.com/eddiethedean/fluxlit/tree/main/tests).
