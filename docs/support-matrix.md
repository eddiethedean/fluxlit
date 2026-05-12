# Support matrix

Published combinations for **FluxLit 0.11.x** on PyPI. Outside this matrix, installs may work but are **best-effort** until tested in CI.

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
| **FastAPI** / **Starlette** | Lower bounds in `pyproject.toml` (`fastapi>=0.111`, `starlette>=0.37`); CI resolves within those ranges. |
| **httpx** / **anyio** | `httpx>=0.27`, `anyio>=4.0` — gateway proxy and async tests. |
| **Streamlit** | `streamlit>=1.36` at runtime; gateway proxies HTTP + WebSockets to Streamlit’s server. You **do not** need `streamlit[starlette]` for FluxLit: the public ASGI app is FastAPI/Starlette; Streamlit runs as a managed sidecar. |
| **Uvicorn** | `uvicorn[standard]>=0.29` — unified entry uses Uvicorn’s HTTP stack; `workers` > 1 unsupported for one FluxLit process. |
| **Pydantic Settings** | `pydantic-settings>=2.0` — `FluxlitSettings` and env loading. |

## Pinning in production apps

FluxLit sits between **FastAPI**, **Streamlit**, **Uvicorn**, **Starlette**, **httpx**, and optional **PyJWT** / **prometheus-client**. Unpinned transitive upgrades can change Streamlit navigation, `AppTest` behavior, or gateway timing.

**Recommended practices:**

1. **Lock the environment** your image or VM runs — for example **`uv lock`** / **`uv sync`**, **`pip-tools`** (`pip-compile` on a `requirements.in`), or a **`constraints.txt`** that pins `fluxlit` plus your direct app dependencies.
2. **Record the versions** you shipped (`pip freeze` or `uv export`) next to each release tag so regressions are bisectable.
3. **Re-run** your test suite (including `FluxLitTestClient` and any Streamlit `AppTest` flows) after any minor Streamlit or Starlette bump; use **`fluxlit doctor`** and **`fluxlit config`** after changing proxy or URL settings.

Minimal **`requirements.in`** sketch (adjust pins to your policy):

```text
fluxlit>=0.11,<1.0
streamlit>=1.36
```

After each FluxLit PyPI release, align this sketch with the current minor (for example ``fluxlit>=0.11,<1.0`` until you adopt **0.12**).

Then `pip-compile requirements.in -o requirements.txt` and install from **`requirements.txt`** in containers.

## Testing and compatibility

- **`FluxLitTestClient`** exercises the same gateway prefix and `/api` mounting as production; keep its version aligned with the FluxLit line you use.
- **Streamlit `AppTest`** APIs evolve between Streamlit minors; pin Streamlit in CI to the same range you run in production, and consult {doc}`testing` for markers and version skips.

## Upgrades and release notes

- **FluxLit:** follow {doc}`changelog` and GitHub **Releases** for behavior changes and dependency-related notes.
- **Upstream bumps:** when you widen pins, run **`ruff`**, **`mypy`** (on your app), and **`pytest`**; enable **`FLUXLIT_TESTS=1`** where AppTest runs unless you intentionally exercise URL sessions (see {doc}`testing`).

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
