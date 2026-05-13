# Command-line interface

The `fluxlit` console script (or `python -m fluxlit`) is built with Typer.

## Setup

```{include} _generated/setup.txt
:literal:
```

## CLI help (real output)

```bash
fluxlit --help
```

```{include} _generated/fluxlit_help_entrypoint.txt
:literal:
```

```{tip}
**`fluxlit dev`** — local development; optional `--reload` and `--reload-scope`. **`fluxlit run`** — production-style process (no reloader). **`fluxlit workbench`** (or **`--workbench`** on `dev` / `run`) — Posit Workbench / Connect-style proxy headers plus a printed loopback URL hint. All start the same **gateway + Streamlit** stack.
```

## Resolving `target`

The optional **`[target]`** argument is a **`module:attribute`** import path (e.g. `app:app`) pointing at your {class}`~fluxlit.app.FluxLit` instance.

Resolution order:

1. Explicit CLI argument, if given.
2. **`target`** from **`fluxlit.toml`** or **`[tool.fluxlit]`** in **`pyproject.toml`** (if present).
3. Literal **`app:app`**.

The working directory should be the project root so Python can import the module. Use **`PYTHONPATH`** or **`pip install -e .`** for src-layout packages.

## Commands

| Command | Description |
|---------|-------------|
| `fluxlit dev [target]` | Development: Streamlit subprocess + gateway. See reload options below. |
| `fluxlit run [target]` | Production-style: same stack, **no** Uvicorn reload. |
| `fluxlit workbench [target]` | Same as ``run`` with Workbench/Connect defaults: trusted proxy headers + startup URL hints. |
| `fluxlit doctor [target]` | Static diagnostics (imports, bind, env). See **Doctor** below. |
| `fluxlit config [target]` | Effective resolved settings (redacted), binding, and warnings; **`--json`**, **`--strict`**. |
| `fluxlit build [target]` | Writes `Dockerfile` + `.dockerignore`; refuses to overwrite without **`--force`**. |
| `fluxlit new <name>` | Creates `<name>/app.py`; use `--profile minimal`, `auth-ready`, or `deploy`. |
| `fluxlit shutdown` | Stops a running `dev` / `run` using the PID file (see below). |

## Common options (`dev` / `run`)

- `--host`, `--port`, `--log-level`
- `--debug` — sets ``FLUXLIT_DEBUG=1`` before loading the app (gateway access logs, API request logging, default log level ``debug`` when still ``info``, ``GET /__fluxlit/debug``, ``get_client`` request-id propagation); see {doc}`configuration` and {doc}`troubleshooting`
- `--workbench` — Posit Workbench / Connect-style: enable Uvicorn ``proxy_headers`` and print loopback URL hints (see {doc}`platforms`)
- `--proxy-headers`, `--forwarded-allow-ips` (Uvicorn / reverse proxy trust)
- `--pidfile` / `--no-pidfile` — PID file path for **`fluxlit shutdown`** (default file or `FLUXLIT_PIDFILE`; skip with `--no-pidfile` or `FLUXLIT_NO_PIDFILE=1`)

Environment-only knobs (no matching CLI flag) still apply: for example **`FLUXLIT_UVICORN_GRACEFUL_SHUTDOWN_TIMEOUT_S`**, when set, is forwarded to Uvicorn as **`timeout_graceful_shutdown`** — see {doc}`deployment` and {doc}`configuration`.

## `shutdown`

**`fluxlit shutdown`** sends **SIGTERM** to the process recorded in the PID file (then optional **SIGKILL** with **`--force`** after **`--wait`** seconds). Use the same working directory and **`--pidfile`** as the server, or set **`FLUXLIT_PIDFILE`** to an absolute path.

On **Windows**, **`--force` runs ``taskkill /T /F``** (POSIX uses ``SIGKILL``). If shutdown still fails, use Task Manager or ``taskkill`` manually.

## Doctor

**`fluxlit doctor`** prints one line per check with **PASS**, **WARN**, or **FAIL**.

- Exits **`1`** if any check is **FAIL**, unless **`--warnings-only`** is set (then always **0**).
- **WARN** does not fail the run; fix when practical (Streamlit version, proxy trust on subpaths, etc.).
- **`--strict`** upgrades selected **WARN** checks to **FAIL**: **`forwarded_allow_ips`** when `trust_proxy` is on but **`FLUXLIT_FORWARDED_ALLOW_IPS`** is unset or **`*`**, and **`public_base_url`** when its URL path does not match **`root_path`** / public mount. Use in CI when you want production-style gates without treating every advisory as blocking.
- Use **`--json`** in CI or deployment scripts for a stable machine-readable shape:

```bash
fluxlit doctor app:app --json
```

With **`--verbose`** (or **`-v`**), plain-text mode prints an extra **Verbose** section after the
check table (redacted settings, resolved bind, discovered pages, OpenAPI paths, URL-session
env flags, and short hints). Combine with **`--json`** to add a top-level **`verbose`** object
(same redacted snapshot) for machines.

The JSON object contains `status`, `target`, `warnings_only`, and a `checks` array
with `name`, `status`, and `detail` for each diagnostic. With **`--verbose`**, it also
includes **`verbose`** (omit **`--verbose`** to keep JSON minimal).

Doctor checks are additive. Current diagnostics include import resolution, the loaded
module file path, the first few `sys.path` entries, ambiguous `app` / `main` candidates,
gateway bind availability, effective API prefix, URL-session test/disable state, proxy
fields, public-base-url precedence, optional auth/metrics extras, Streamlit upstream
state when available, readiness route shape, WebSocket upgrade expectations, gateway
upstream timeout hints, async page-depends posture, optional client-header forwarding
(including **`gateway_forward_rejected_names`** when the allowlist names headers that
are never forwarded), and (with **`--verbose`**) a compact **`gateway_proxy`** summary
block (timeouts, max proxied body bytes, max concurrent upstream HTTP, forward-header list).

**`fluxlit config`** mirrors related **WARN** rows (for example rejected forward-header
names and **`trust_proxy`** with an unlimited proxied upload body cap); use **`--strict`**
in CI to fail on warnings — see {doc}`cookbook`.

## Reload (`dev` only)

`--reload` enables Uvicorn’s file watcher. Scope is controlled by **`--reload-scope`**:

| Value | Behavior |
|-------|----------|
| `gateway` (default) | Only the ASGI gateway process reloads; Streamlit keeps running. |
| `full` | Gateway reload **and** Streamlit sidecar restart on changes (uses `watchfiles`; WebSockets reconnect). |

Example:

```bash
fluxlit dev --reload --reload-scope=full
```

`full` is best-effort dev ergonomics; for production use `fluxlit run` without reload.

Unknown scopes are rejected by the CLI and again in the runtime before the Streamlit subprocess starts.

## `build`

- **`--output` / `-o`** — directory for generated files (default: current directory).
- **`--force` / `-f`** — overwrite existing `Dockerfile` / `.dockerignore`.
- The **`target`** embedded in `CMD` follows the same resolution rules as other commands.

The template ships with a **digest-pinned** `python:3.12-slim` base and **`USER appuser`** (UID 1000). For production, add your own **dependency lockfile** (`pip-tools`, `uv`, Poetry export, etc.); see {doc}`deployment` and **`examples/docker_compose/`** for a `pip-compile` example. You can still switch to multi-stage builds or a different base by editing the generated files.

## Entry point

The Typer application lives in {mod}`fluxlit.cli`; the console script calls {func}`~fluxlit.cli.main`.
