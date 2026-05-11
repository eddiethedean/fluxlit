# Command-line interface

The `fluxlit` console script (or `python -m fluxlit`) is built with Typer.

```{tip}
**`fluxlit dev`** — local development; optional `--reload` and `--reload-scope`. **`fluxlit run`** — production-style process (no reloader). Both start the same **gateway + Streamlit** stack.
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
| `fluxlit doctor [target]` | Static diagnostics (imports, bind, env). See **Doctor** below. |
| `fluxlit build [target]` | Writes `Dockerfile` + `.dockerignore`; refuses to overwrite without **`--force`**. |
| `fluxlit new <name>` | Creates `<name>/app.py` with a minimal demo. |
| `fluxlit shutdown` | Stops a running `dev` / `run` using the PID file (see below). |

## Common options (`dev` / `run`)

- `--host`, `--port`, `--log-level`
- `--proxy-headers`, `--forwarded-allow-ips` (Uvicorn / reverse proxy trust)
- `--pidfile` / `--no-pidfile` — PID file path for **`fluxlit shutdown`** (default file or `FLUXLIT_PIDFILE`; skip with `--no-pidfile` or `FLUXLIT_NO_PIDFILE=1`)

## `shutdown`

**`fluxlit shutdown`** sends **SIGTERM** to the process recorded in the PID file (then optional **SIGKILL** with **`--force`** after **`--wait`** seconds). Use the same working directory and **`--pidfile`** as the server, or set **`FLUXLIT_PIDFILE`** to an absolute path.

On **Windows**, **`--force` does not send SIGKILL** (POSIX only). If the process is still running after the wait window, stop it from Task Manager or `taskkill` as appropriate.

## Doctor

**`fluxlit doctor`** prints one line per check with **PASS**, **WARN**, or **FAIL**.

- Exits **`1`** if any check is **FAIL**, unless **`--warnings-only`** is set (then always **0**).
- **WARN** does not fail the run; fix when practical (Streamlit version, proxy trust on subpaths, etc.).

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

Customize the generated Dockerfile for multi-stage builds, non-root users, and dependency installs (`requirements.txt`, Poetry, etc.).

## Entry point

The Typer application lives in {mod}`fluxlit.cli`; the console script calls {func}`~fluxlit.cli.main`.
