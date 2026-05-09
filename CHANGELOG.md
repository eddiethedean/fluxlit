# Changelog

## 0.2.0

- **Config:** `fluxlit.toml` and `pyproject.toml` `[tool.fluxlit]` for default `target`, bind options, and log level (`fluxlit.project_config`). Precedence: CLI → environment → project file → defaults.
- **CLI:** `fluxlit build` writes a starter `Dockerfile` and `.dockerignore`; `fluxlit doctor` reports PASS/WARN/FAIL checks (import, port bind, deps, `FLUXLIT_INTERNAL_API_BASE`) with optional `--warnings-only`.
- **CLI:** `fluxlit dev` / `run` accept an omitted `target` when configured in a project file; `--reload-scope=gateway` documents gateway-only reload; stderr warns that Streamlit does not reload.
- **Pages:** `FluxLit.discover_pages(directory, package=...)` imports sibling modules and calls `register(app)` for opt-in multipage packages.
- **Client:** `ApiClient.get_model` / `post_model` for Pydantic-validated JSON.
- **Observability:** Gateway sets a request id from `X-Request-ID` (or generates one) via `logging_context`; optional `FluxlitSettings.enable_request_logging` adds FastAPI access logs at INFO.
- **Dependencies:** `tomli` on Python 3.10 for TOML parsing (stdlib `tomllib` on 3.11+).

## 0.1.0

- Unified gateway + sidecar runtime (single public port; HTTP + WebSocket proxy to Streamlit).
- CLI: `dev`, `run`, `new`, `doctor`.
- Configurable API prefix (`api_mount_path` / gateway `api_prefix`) with `/api` default.
- Runtime hardening (gateway stops if Streamlit exits; improved shutdown behavior).
- Testing support:
  - FluxLit-native `FluxLitTestClient`
  - FastAPI/Starlette TestClient tests for gateway routing
  - Streamlit AppTest coverage (version-dependent)
  - CLI + ApiClient contract tests
- CI (GitHub Actions) and contributor docs.

## Unreleased

- **Docs:** Sphinx + MyST site under `docs/`, optional `pip install -e ".[docs]"`, Read the Docs config (`.readthedocs.yaml`), CI `docs` job, PyPI `Documentation` URL points to RTD.
