# Changelog

## Unreleased

- Configurable API prefix in the gateway (`api_mount_path` / `api_prefix`).
- Runtime hardening: stop gateway if Streamlit exits; wire `log_level`, `proxy_headers`, `forwarded_allow_ips`.
- Added `fluxlit doctor`.
- Added `FluxLitTestClient` and expanded tests (FastAPI TestClient + Streamlit AppTest + CLI + client contracts).
- Added CI (GitHub Actions) and contributor docs.

## 0.1.0

- Initial alpha: unified gateway, CLI (`dev/run/new`), tests, typed packaging.
