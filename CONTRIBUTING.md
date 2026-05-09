# Contributing to FluxLit

Thanks for helping improve FluxLit.

## Setup

```bash
git clone https://github.com/odosmatthews/fluxlit.git
cd fluxlit
python -m pip install -e ".[dev]"
```

## Quality checks

```bash
ruff check src tests
ruff format src tests
python -m pytest
python -m mypy src/fluxlit
```

## Documentation (Sphinx)

Hosted on [Read the Docs](https://fluxlit.readthedocs.io/en/stable/) once the project is connected to this repository.

Build locally:

```bash
python -m pip install -e ".[docs]"
sphinx-build -b html docs docs/_build/html
```

Open `docs/_build/html/index.html` in a browser. Configuration lives in [`docs/conf.py`](docs/conf.py); `.readthedocs.yaml` drives RTD builds.

## Testing notes

- Prefer FluxLit’s wrapper **`FluxLitTestClient`** for gateway-level API tests (so prefix stripping and `/healthz` behavior are exercised through the gateway).
- Use Streamlit’s built-in **`streamlit.testing.v1.AppTest`** for UI tests where possible (version-dependent).

## Design constraints

- Keep FluxLit **sidecar-first** (Streamlit subprocess + gateway) until an embedded ASGI story is proven stable.
- Avoid adding opinionated “magic” around FastAPI and Streamlit—prefer small, composable helpers.
- Treat WebSocket proxy stability as a first-class requirement.

## Reload behavior

`fluxlit dev --reload` uses Uvicorn’s reloader on the gateway factory only. The Streamlit child process is **not** restarted automatically; document this when changing runtime or UX code paths.

## Pull requests

- Include tests when changing routing/runtime behavior.
- Update docs (`README.md`, `docs/`, `FLUXLIT_PLAN.md`, `FLUXLIT_ROADMAP.md`) when you change public behavior.
