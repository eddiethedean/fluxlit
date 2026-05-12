# Troubleshooting

**Quick links:** [Doctor](#first-step-fluxlit-doctor) · [Import errors](#import-and-target-errors) · [Port in use](#port-already-in-use) · [503 on readyz](#readiness-returns-503) · [413 / 502 from gateway](#payload-too-large-or-bad-gateway-from-the-proxy) · [Streamlit ↔ API](#streamlit-cannot-reach-the-api) · [Debug mode](#debug-mode-streamlit-api-connectivity) · [Proxy / subpath](#subpath-static-assets-websockets) · [Auth](#authentication) · {doc}`runbooks` · {doc}`production-tls` · {doc}`secrets`

## First step: `fluxlit doctor`

Run **`fluxlit doctor`** (optionally with your `module:app` target). It reports **PASS**, **WARN**, or **FAIL** for imports, dependencies, gateway bind, `FLUXLIT_INTERNAL_API_BASE`, Streamlit version, JWT/OIDC env vs PyJWT, and subpath/proxy hints.

- **Exit code 1** if any row is **FAIL** (unless `--warnings-only`).
- **WARN** rows are advisory (e.g. old Streamlit, subpath without `trust_proxy`, CORS without security headers).

## Import and target errors

**`import_target` FAIL**

- Check the **`target`** string (`app:app`): module must be importable from the current working directory (`PYTHONPATH` / `pip install -e .`).
- Run from the project root where `fluxlit.toml` or your package lives.
- In monorepos, avoid putting sibling services with top-level `app` or `main` packages
  on `PYTHONPATH` at the same time. `fluxlit doctor` warns when multiple importable
  candidates are visible for the same top-level target.

**Multiple `app` / `main` candidates**

- Prefer an explicit package target such as `my_service.main:app`, or run tests with
  only the intended project root prepended to `sys.path`.
- If your entrypoint is a top-level file, FluxLit prefers `./main.py` or `./app.py`
  from the current working directory and prepends that file's directory before
  executing it, so sibling imports work without a global `PYTHONPATH`.
- For Pytest, clear stale modules only when you intentionally swap project roots in
  one process; most suites should use one project root per test session.

**`ValueError` / `reload_scope`**

- With `--reload`, only **`gateway`** and **`full`** are valid. Typer exits **2** on invalid CLI values; the runtime validates again before starting Streamlit.

## Port already in use

**`gateway_bind` FAIL**

- Another process holds the host:port. Free the port or change **`--port`** / `FLUXLIT_GATEWAY_PORT` / `fluxlit.toml` `gateway_port`.
- On shared hosts, ensure only one `fluxlit run` binds the same address.

## Readiness returns 503

**`GET /api/readyz` → 503** under the unified runtime usually means the **Streamlit upstream** is down, not accepting HTTP (crash, slow start, wrong URL), or returned a **non-2xx** status for `GET` on the upstream root (readiness expects **2xx**).

- Confirm **`fluxlit run`** is the entrypoint (upstream env is set by the parent).
- Check Streamlit logs from the same process tree.
- Temporarily hit **`GET /api/healthz`**: if 200 but `readyz` is 503, the API process is fine; the sidecar is not.

In **unit tests** without `FLUXLIT_STREAMLIT_UPSTREAM`, `readyz` may return **200** with `not_configured` — that is expected.

## Payload too large or bad gateway from the proxy

- **`413 Payload Too Large`** on paths proxied to Streamlit means the request body exceeded **`FLUXLIT_GATEWAY_MAX_PROXY_REQUEST_BODY_BYTES`** (or the same setting in `FluxlitSettings`). Raise the limit if large uploads are intentional, or upload via the API instead of through the Streamlit proxy.
- **`502 Bad Gateway`** on proxied routes usually means the gateway could not complete the upstream HTTP call (connection refused, timeouts, TLS errors, etc.). Check **`FLUXLIT_GATEWAY_UPSTREAM_CONNECT_TIMEOUT_S`** / **`FLUXLIT_GATEWAY_UPSTREAM_READ_TIMEOUT_S`**, Streamlit health, and network path to the sidecar. See {doc}`configuration` and {doc}`observability` (request ids in logs).

## Streamlit cannot reach the API

**404**, **connection errors**, or empty responses from `client.get("/...")` in `@app.page` handlers:

- Use paths **without** duplicating the API prefix: `client.get("/users")`, not `client.get("/api/users")`. The runtime sets `FLUXLIT_INTERNAL_API_BASE` to include `/api`.
- If you override **`FLUXLIT_INTERNAL_API_BASE`** manually (unusual), it must be an absolute URL whose path matches `api_mount_path` (default `/api`). Doctor warns on mismatch.
- In Pytest, prefer the patterns in {doc}`testing` so `FluxLitTestClient`,
  `AppTest`, `FLUXLIT_APP`, and the API prefix are configured consistently.

## Debug mode (Streamlit ↔ API connectivity)

Use **`FLUXLIT_DEBUG=1`** or **`fluxlit dev` / `run` / `workbench --debug`** for a single switch that tightens logging and surfaces a **redacted** snapshot at **`GET /__fluxlit/debug`** (effective gateway prefix, mount, settings summary, recent gateway dispatch rows). The parent process also prints **`[fluxlit-debug]`** to stderr with the derived internal API base and mount so you can confirm Streamlit and the gateway agree on URLs.

- **`get_client()`** forwards **`X-Request-ID`** to `/api` when debug is on so API logs line up with the browser request (advanced correlation).
- If **`api_mount_path`** equals **`/__fluxlit/debug`** or is a prefix of it, the debug HTTP route is **disabled** (returns 404) so your API keeps that path.
- Turn debug off in production unless you intend the extra logs and the snapshot endpoint; treat **`/__fluxlit/debug`** like internal diagnostics (see {doc}`secrets`).

## Subpath / static assets / WebSockets

**Broken CSS, `/_stcore` errors, or wrong links** behind a reverse proxy:

- Set **`FLUXLIT_ROOT_PATH`** to the browser-visible prefix (no trailing slash).
- Enable **`FLUXLIT_TRUST_PROXY=1`** (or `--proxy-headers`) so scheme and host match the public URL.
- For OAuth, set **`FLUXLIT_PUBLIC_BASE_URL`** to the public origin.

See {doc}`configuration` (reverse proxies) and {doc}`production-tls` (forwarded headers, HSTS, validating TLS the same way as production).

## Authentication

**`fluxlit_auth_extra` FAIL** with JWT-related env set

- Install **`pip install "fluxlit[auth]"`** so PyJWT is available.

**`fluxlit_metrics_extra` FAIL** with gateway metrics enabled

- Install **`pip install "fluxlit[metrics]"`** so `prometheus-client` is available, or
  unset `FLUXLIT_ENABLE_GATEWAY_PROMETHEUS_METRICS`.

**`public_base_url_precedence` WARN / FAIL**

- Prefer `FLUXLIT_PUBLIC_BASE_URL` for FluxLit OAuth redirects. `PUBLIC_BASE_URL` is
  only a fallback for platforms that already provide it.
- If both are set differently, FluxLit uses `FLUXLIT_PUBLIC_BASE_URL`. Set
  `FLUXLIT_STRICT_PUBLIC_BASE_URL=1` in deployment checks when a mismatch should fail
  `fluxlit doctor`.

**401 / 403 from API while developing**

- The default **`client`** injected into pages does not send **Authorization**. Use :meth:`fluxlit.client.ApiClient.with_bearer`, :meth:`fluxlit.client.ApiClient.for_fluxlit`, an `auth_header_factory`, or {func}`~fluxlit.streamlit_auth.prepare_streamlit_api_client` after OIDC — {doc}`auth-recipes` and {doc}`streamlit-api-client`.

## Development reload confusion

- **`--reload-scope=gateway`** (default): only the gateway reloads; **Streamlit keeps old code** until you restart the process.
- **`--reload-scope=full`**: restarts Streamlit on file changes; requires **`watchfiles`** installed.

## PID file and shutdown

If **`fluxlit shutdown`** cannot find the process, use the same **`--pidfile`** (or `FLUXLIT_PIDFILE`) and working directory as `dev` / `run`. See {doc}`cli`.

On **Windows**, the first stop attempt uses ``taskkill /T``; with **`--force`**, FluxLit runs ``taskkill /T /F``. If the PID file targets a process your shell cannot stop, use Task Manager or an elevated prompt.

## Getting help

- {doc}`architecture` — routing and sidecar model.
- {doc}`deployment` — probes and containers.
- {doc}`runbooks` — production-style incidents (`readyz`, blank UI, WebSockets, auth).
- {doc}`production-tls` — reverse-proxy TLS and header trust.
- {doc}`secrets` — avoiding credential leaks in logs; key rotation.
- Repository **Issues** on GitHub for bugs; **Discussions** for usage questions if enabled.
