# Command-line interface

The `fluxlit` console script (or `python -m fluxlit`) is built with Typer.

## Commands

| Command | Description |
|---------|-------------|
| `fluxlit dev [target]` | Development: Streamlit subprocess + gateway. `target` defaults from project file, then `app:app`. |
| `fluxlit run [target]` | Same stack without auto-reload. |
| `fluxlit doctor [target]` | Checks import, dependencies, port bind, `FLUXLIT_INTERNAL_API_BASE`. Exits `1` on failure unless `--warnings-only`. |
| `fluxlit build [target]` | Writes a starter `Dockerfile` and `.dockerignore` (`--output` / `-o`, `--force`). |
| `fluxlit new <name>` | Scaffold a minimal `app.py` in a new directory. |

## Common options (`dev` / `run`)

- `--host`, `--port`, `--log-level`
- `--proxy-headers`, `--forwarded-allow-ips` (Uvicorn / reverse proxy trust)

## Reload (`dev` only)

`--reload` restarts the **API gateway** via Uvicorn’s reloader. The **Streamlit subprocess is not restarted**. A warning is printed on startup. Only `--reload-scope=gateway` is supported today.

Restart the `fluxlit` process to pick up Streamlit-only changes reliably.

## Entry point

The Typer application lives in {mod}`fluxlit.cli`; the console script calls {func}`~fluxlit.cli.main`.
