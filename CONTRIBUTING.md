# Contributing to FluxLit

Thanks for helping improve FluxLit.

## Setup

```bash
git clone https://github.com/eddiethedean/fluxlit.git
cd fluxlit
python -m pip install -e ".[dev]"
```

## Public API stability

Refactors should keep the **documented public surface** stable unless you are shipping a semver breaking release (see **Releases** below).

- **Stable:** symbols exported from [`src/fluxlit/__init__.py`](src/fluxlit/__init__.py), the `fluxlit` CLI entrypoint ([`src/fluxlit/cli.py`](src/fluxlit/cli.py)), and documented kwargs on `FluxLit`, `build_gateway`, `run_unified`, and related settings types.
- **Internal:** names prefixed with a single leading underscore (e.g. `_proxy_http` used only in tests), anything under a `fluxlit._*` package if introduced later, and modules not listed in `__all__`. Prefer extending behavior via new optional parameters or new public helpers rather than renaming stable entrypoints.

## Quality checks

```bash
ruff check src tests
ruff format src tests
python -m pytest -n auto -m "not slow"
python -m mypy src/fluxlit
```

Optional **[ty](https://docs.astral.sh/ty/)** (Astral static analysis; CI runs it as a non-blocking signal): `pip install ty` and `ty check` from the repo root after `pip install -e ".[metrics]"` if you want optional imports resolved. CI pins `ty` to match local expectations. For **stricter** checking on `tests/` (same rules as `src/`), run `ty check --config-file ty.strict-tests.toml` (may report many diagnostics until tests are tightened).

Coverage (optional): `pytest -n auto --cov=fluxlit --cov-report=term-missing`. See [docs/testing.md](docs/testing.md) for markers, E2E, Docker proxy smoke, and the **`--cov-fail-under`** gate used on CI.

## Documentation (Sphinx)

Hosted on [Read the Docs](https://fluxlit.readthedocs.io/en/stable/) once the project is connected to this repository. User-facing guides include **[docs/deployment.md](docs/deployment.md)** (containers, probes, scaling), **[docs/troubleshooting.md](docs/troubleshooting.md)**, **[docs/production-tls.md](docs/production-tls.md)** (TLS, HSTS, `forwarded_allow_ips`, CSP notes, path-prefixed mounts such as **`/apps/my-app`**), **[docs/secrets.md](docs/secrets.md)** (logs, secret stores, JWT/OIDC rotation), and runnable nginx + FluxLit stacks under **[docker/proxy-deployment/](docker/proxy-deployment/)** (validated by **`run-all-proxy-smokes.sh`** in CI).

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
- **CI** runs **`pip-audit`** on `pip install -e ".[auth]"` and uploads a **CycloneDX JSON** SBOM for the same environment (artifact **`cyclonedx-sbom`** on the `security-audit` workflow run). See **SECURITY.md** for download notes.
- Optional local dependency audit (**same scope as CI** — core + `auth`):

  ```bash
  python -m pip install pip-audit
  python -m pip install -e ".[auth]"
  pip-audit
  ```

  For a broader scan (includes dev/docs/Streamlit transitive deps), install `".[dev,auth,docs]"` before `pip-audit`.

- When you change **`examples/docker_compose/requirements.in`**, regenerate **`requirements.txt`** with **`pip-compile`** (see that example’s README) so the Docker image stays reproducible.

## Releases (maintainers)

For a **PyPI / tag** release of FluxLit itself:

1. **CHANGELOG** — add a dated section under `CHANGELOG.md` (move items from **Unreleased** if present).
2. **Version** — bump `version` in `pyproject.toml` (semver **0.x**; document breaking changes in CHANGELOG). Keep **`src/fluxlit/__init__.py`** `__version__` identical so imports and `fluxlit doctor` stay consistent; CI’s docs job regenerates `docs/_generated/setup.txt` from `importlib.metadata.version("fluxlit")`, which must match the committed file after `pip install -e .`.
3. **Upgrade note** — if CLI, env, import behavior, or defaults changed, add a short **“Upgrading from X.Y.Z”** note in CHANGELOG (commands to run, renamed env vars, removed shims, and test-layout notes).
4. **Tag** — `git tag vX.Y.Z` after merge to the release branch / `main` per your workflow.
5. **Read the Docs** — confirm the **stable** build points at the new tag when applicable.

6. **Examples lockfile** — after the wheel is on PyPI, bump **`examples/docker_compose/requirements.in`** (for example `fluxlit>=0.10,<1.0`) and run **`uv pip compile examples/docker_compose/requirements.in -o examples/docker_compose/requirements.txt`** so the pinned example matches installable releases.

Before tagging, run the canonical smoke app once locally when runtime or deployment behavior
changed:

```bash
./scripts/run_smoke_app.sh
BASE_URL=http://127.0.0.1:8000 PATH_SUFFIX=/api/smoke COUNT=50 ./scripts/soak_http.sh
```

Support expectations for Python and dependencies are summarized in **`docs/support-matrix.md`**.

## Public-facing polish checklist

Before merging changes that affect user-visible behavior, check the public surface for drift:

1. **README and docs entry points** — keep `README.md`, `docs/index.md`, and `docs/quickstart.md` aligned on install commands, default port (`8000`), API prefix (`/api`), and the recommended first run.
2. **Roadmap and changelog** — when a feature moves from planned to shipped, update both `CHANGELOG.md` and `ROADMAP.md`; avoid leaving “TBD” or “not implemented yet” language for released behavior.
3. **Examples** — verify example READMEs use the gateway URL FluxLit prints, not Streamlit’s internal sidecar port.
4. **Generated snippets** — regenerate `docs/_generated/` snippets when CLI help or setup output changes.
5. **Links** — prefer relative links inside repository Markdown; use canonical GitHub URLs when the rendered docs need to point readers back to source files, workflows, or security advisories.

## Pull requests

- Include tests when changing routing/runtime behavior.
- Update docs (`README.md`, `docs/`, `PLAN.md`, `ROADMAP.md`) when you change public behavior.
