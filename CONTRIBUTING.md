# Contributing to FluxLit

Thanks for helping improve FluxLit.

## Setup

```bash
git clone https://github.com/eddiethedean/fluxlit.git
cd fluxlit
python -m pip install -e ".[dev]"
```

## Quality checks

```bash
ruff check src tests
ruff format src tests
python -m pytest -n auto -m "not slow"
python -m mypy src/fluxlit
```

Coverage (optional): `pytest -n auto --cov=fluxlit --cov-report=term-missing`. See [docs/testing.md](docs/testing.md) for markers, E2E, and Docker proxy smoke.

## Documentation (Sphinx)

Hosted on [Read the Docs](https://fluxlit.readthedocs.io/en/stable/) once the project is connected to this repository. User-facing guides include **[docs/deployment.md](docs/deployment.md)** (containers, probes, scaling) and **[docs/troubleshooting.md](docs/troubleshooting.md)**.

Build locally:

```bash
python -m pip install -e ".[docs]"
sphinx-build -b html docs docs/_build/html
```

Open `docs/_build/html/index.html` in a browser. Configuration lives in [`docs/conf.py`](docs/conf.py); `.readthedocs.yaml` drives RTD builds.

## Testing notes

Full guide: **[docs/testing.md](docs/testing.md)** (coverage, `e2e` / `slow` markers, Playwright, proxy smoke, [fast suite highlights](docs/testing.md#fast-suite-highlights)). Dev reload: `fluxlit dev --reload --reload-scope=full` restarts Streamlit on changes; default `gateway` reloads FastAPI only — see **docs/cli.md**.

- Prefer FluxLit’s wrapper **`FluxLitTestClient`** for gateway-level API tests (so prefix stripping and `/healthz` behavior are exercised through the gateway).
- Use Streamlit’s built-in **`streamlit.testing.v1.AppTest`** for UI tests where possible (version-dependent).

## Design constraints

- Keep FluxLit **sidecar-first** (Streamlit subprocess + gateway) until an embedded ASGI story is proven stable.
- Avoid adding opinionated “magic” around FastAPI and Streamlit—prefer small, composable helpers.
- Treat WebSocket proxy stability as a first-class requirement.

## Reload behavior

`fluxlit dev --reload` uses Uvicorn’s reloader on the gateway factory only. The Streamlit child process is **not** restarted automatically; document this when changing runtime or UX code paths.

## Security

- Report undisclosed vulnerabilities privately per [`SECURITY.md`](SECURITY.md) (GitHub Security Advisories), not via a public issue.
- Optional local dependency audit (**same scope as CI** — core + `auth`):

  ```bash
  python -m pip install pip-audit
  python -m pip install -e ".[auth]"
  pip-audit
  ```

  For a broader scan (includes dev/docs/Streamlit transitive deps), install `".[dev,auth,docs]"` before `pip-audit`.

## Pull requests

- Include tests when changing routing/runtime behavior.
- Update docs (`README.md`, `docs/`, `PLAN.md`, `ROADMAP.md`) when you change public behavior.
