# Support matrix

Published combinations for **FluxLit 0.5.x** on PyPI. Outside this matrix, installs may work but are **best-effort** until tested in CI.

## Python

| Python | CI (main branch) |
|--------|------------------|
| 3.10 | Ubuntu, macOS, Windows matrix |
| 3.11 | Ubuntu, macOS, Windows matrix |
| 3.12 | Ubuntu, macOS, Windows matrix + docs + security-audit + proxy smoke |
| 3.13 | Ubuntu, macOS, Windows matrix |

## Core dependencies (approximate)

CI installs **`pip install -e ".[dev]"`** from `pyproject.toml` pins and the resolver’s chosen versions. For **latest** upstream smoke (Streamlit / FastAPI / Starlette upgraded after install), see the **`upgrade-smoke`** workflow in `.github/workflows/upgrade-smoke.yml` — it is **non-blocking** and runs on a schedule or manual dispatch.

| Package | Notes |
|---------|--------|
| **FastAPI** / **Starlette** | Lower bounds in `pyproject.toml`; upper bounds follow resolver in lock-free dev install. |
| **Streamlit** | Required at runtime; gateway proxies HTTP + WebSockets to Streamlit’s server. |
| **Uvicorn** | Unified entry uses Uvicorn’s HTTP stack; `workers` > 1 unsupported for one FluxLit process. |

## Optional extras

| Extra | Purpose |
|-------|---------|
| **`fluxlit[auth]`** | PyJWT, cryptography — JWT/OIDC helpers; same tree **`pip-audit`** / SBOM use in CI. |
| **`fluxlit[metrics]`** | `prometheus-client` — gateway RED metrics endpoint. |
| **`fluxlit[e2e]`** | Playwright — browser tests under `tests/e2e`. |

## Long-term support (LTS)

There is **no LTS branch** for **0.x** today; security and fixes land on the **current minor** on PyPI. If you need extended support for an older line, open a discussion with maintainers.

## Related

- {doc}`testing` — CI layout, upgrade smoke, soak scripts.
- {doc}`contributing` — release and upgrade checklist.
