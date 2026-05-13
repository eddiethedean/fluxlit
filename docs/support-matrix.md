# Support matrix

Published combinations for **FluxLit 0.13.x** on PyPI. Outside this matrix, installs may work but are **best-effort** until tested in CI.

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
| **httpx** / **anyio** | `httpx>=0.27`, `anyio>=4.0` — gateway proxy and async tests. `ApiClient` imports a few **typing-only** symbols from `httpx._types` / `httpx._client` to mirror ``Client.request`` annotations; treat these as **intentional** until httpx exposes stable public aliases — re-audit on httpx minor bumps (see roadmap dependency hygiene). |
| **Streamlit** | `streamlit>=1.36` at runtime; gateway proxies HTTP + WebSockets to Streamlit’s server. You **do not** need `streamlit[starlette]` for FluxLit: the public ASGI app is FastAPI/Starlette; Streamlit runs as a managed sidecar. |
| **Uvicorn** | `uvicorn[standard]>=0.29` — unified entry uses Uvicorn’s HTTP stack; **`workers` > 1** is unsupported for one FluxLit process. When you mount the unified {class}`~fluxlit.app.FluxLit` ASGI app under Uvicorn with multiple workers, **lifespan startup fails** unless **`FLUXLIT_ALLOW_UNIFIED_UVICORN_MULTIWORKER=1`** (explicitly unsupported — use one worker per replica and scale out). See {doc}`deployment`. |
| **Pydantic Settings** | `pydantic-settings>=2.0` — `FluxlitSettings` and env loading. |

## Stability charter (operator contract)

FluxLit **0.12.x** documents which emitted names and fields operators may rely on for dashboards, alerts, and CI **without** treating every patch as a breaking change. Anything marked **experimental** may change behavior or shape in a minor release with changelog notice.

### Gateway Prometheus metrics

The canonical list is {data}`fluxlit.gateway.metrics.GATEWAY_PROMETHEUS_METRICS` in code and the **Metrics contract** table in {doc}`observability`.

| Name | Type | Labels | Stability |
|------|------|--------|-----------|
| `fluxlit_gateway_requests_total` | Counter | `dispatch`, `method_kind` | **Stable** (0.x). |
| `fluxlit_gateway_request_duration_seconds` | Histogram | `dispatch` | **Stable** name and labels; bucket changes are semver-visible (see observability). |

### Page manifest (`manifest_version` 1)

Produced by :func:`~fluxlit.pages.manifest.build_page_manifest` (and ``fluxlit pages manifest``). Top-level keys:

| Key | Stability | Notes |
|-----|-----------|-------|
| `manifest_version` | **Stable** | Currently `1`. A future `2` would be a deliberate migration. |
| `manifest_stability` | **Stable** | Declared **stable** for v1 output. |
| `title` | **Stable** | From `FluxlitSettings.title`. |
| `pages` | **Stable** (array shape) | List of page objects; **fields inside each page** below. |

Per **page** object (stable keys; **values** reflect your app):

| Key | Stability | Notes |
|-----|-----------|-------|
| `path`, `title`, `tags`, `description`, `icon` | **Stable** | Registration-time metadata. |
| `parameters` | **Stable** | `{name, annotation}` entries from signatures. |
| `dependencies` | **Stable** | Qualnames of `Depends` targets; no code objects. |
| `children` | **May evolve** | Optional list from `PageMeta.children`; ordering/display rules may gain keys in minors—check changelog when upgrading. |

### Structured log field contracts

| Export | Fields | Stability |
|--------|--------|-----------|
| {data}`fluxlit.logging.JSON_LOG_BASE_FIELDS` | `time`, `level`, `logger`, `message` | **Stable** for JSON formatter output. |
| {data}`fluxlit.logging.GATEWAY_ACCESS_LOG_FIELDS` | `request_id`, `fluxlit_dispatch`, `http_method_or_type`, `path`, `query` | **Stable** for gateway access `extra` when those lines are emitted. |

Header redaction helpers in {mod}`fluxlit.logging.redact` are **behavior-stable** for security (values may show `<redacted>`); exact log **wording** of debug lines is **not** chartered.

### Experimental `FluxlitSettings` fields

| Field / env | Stability | Notes |
|-------------|-----------|-------|
| `experimental_yield_pages` / `FLUXLIT_EXPERIMENTAL_YIELD_PAGES` | **Experimental** | Generator pages run an extra `next()` per script run; may change or be removed after feedback. |
| `async_page_depends` / `FLUXLIT_ASYNC_PAGE_DEPENDS` | **Experimental** | Async `Depends` resolution paths (thread offload when a loop is running) may be refined. |

Promotion to **stable for 1.0** requires: documented semantics, tests, and an explicit roadmap/CHANGELOG decision (no longer gated behind experimental flags).

## Pinning in production apps

FluxLit sits between **FastAPI**, **Streamlit**, **Uvicorn**, **Starlette**, **httpx**, and optional **PyJWT** / **prometheus-client**. Unpinned transitive upgrades can change Streamlit navigation, `AppTest` behavior, or gateway timing.

**Recommended practices:**

1. **Lock the environment** your image or VM runs — for example **`uv lock`** / **`uv sync`**, **`pip-tools`** (`pip-compile` on a `requirements.in`), or a **`constraints.txt`** that pins `fluxlit` plus your direct app dependencies.
2. **Record the versions** you shipped (`pip freeze` or `uv export`) next to each release tag so regressions are bisectable.
3. **Re-run** your test suite (including `FluxLitTestClient` and any Streamlit `AppTest` flows) after any minor Streamlit or Starlette bump; use **`fluxlit doctor`** and **`fluxlit config`** after changing proxy or URL settings.

Minimal **`requirements.in`** sketch (adjust pins to your policy):

```text
fluxlit>=0.13,<1.0
streamlit>=1.36
```

After each FluxLit PyPI release, align this sketch with the current minor (for example ``fluxlit>=0.13,<1.0`` until you adopt **0.14**).

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

## 1.0 compatibility and deprecation

This subsection is the **compatibility contract** for the **1.x** line after **1.0.0**; it is updated when release candidates ship. Until **1.0.0rc1**, treat numbered pre-releases as **draft** if they differ from this text.

- **Semver:** After **1.0.0**, FluxLit follows **semver** for the documented stable surface (CLI, `FLUXLIT_*` keys called out in {doc}`configuration`, and public Python APIs exported from :mod:`fluxlit` and described in guides). **Experimental** settings and **internal** debug logs remain exempt until promoted.
- **Python / Streamlit / core deps:** The [Python](#python) and [Core dependencies](#core-dependencies-approximate) tables become the **compatibility commitment** for 1.x minors unless a release explicitly widens or narrows them.
- **Deprecations:** behavior or config removals will be announced in {doc}`changelog` with a **deprecation window** where practical (at least one minor when feasible).
- **Metrics and manifests:** Gateway metric **names** and **manifest_version** **1** top-level keys above stay stable across 1.x unless a major documents a migration (for example a new manifest version).

## Related

- {doc}`testing` — CI layout, upgrade smoke, soak scripts.
- {doc}`contributing` — release and upgrade checklist.
