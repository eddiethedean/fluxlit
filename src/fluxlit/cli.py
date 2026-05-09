from __future__ import annotations

from pathlib import Path

import typer

from fluxlit.runtime import run_unified

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command()
def dev(
    target: str = typer.Argument("app:app", help="Import path to your FluxLit instance."),
    host: str | None = typer.Option(None, help="Bind address for the unified gateway."),
    port: int | None = typer.Option(None, help="Port for the unified gateway."),
    log_level: str | None = typer.Option(
        None, help="Uvicorn log level (debug, info, warning, error)."
    ),
    proxy_headers: bool = typer.Option(False, help="Trust X-Forwarded-* headers from a proxy."),
    forwarded_allow_ips: str | None = typer.Option(
        None,
        help="Comma-separated IPs to trust for forwarded headers (uvicorn forwarded_allow_ips).",
    ),
    reload: bool = typer.Option(
        False,
        help="Reload the API gateway on code changes (experimental).",
    ),
) -> None:
    """Run FastAPI + Streamlit behind a single ASGI gateway (development)."""
    from fluxlit.runtime import load_fluxlit

    fl = load_fluxlit(target)
    run_unified(
        target,
        host=host or fl.settings.gateway_host,
        port=port or fl.settings.gateway_port,
        reload=reload,
        log_level=log_level or fl.settings.log_level,
        proxy_headers=proxy_headers,
        forwarded_allow_ips=forwarded_allow_ips,
    )


@app.command("run")
def run_cmd(
    target: str = typer.Argument("app:app", help="Import path to your FluxLit instance."),
    host: str | None = typer.Option(None, help="Bind address for the unified gateway."),
    port: int | None = typer.Option(None, help="Port for the unified gateway."),
    log_level: str | None = typer.Option(
        None, help="Uvicorn log level (debug, info, warning, error)."
    ),
    proxy_headers: bool = typer.Option(False, help="Trust X-Forwarded-* headers from a proxy."),
    forwarded_allow_ips: str | None = typer.Option(
        None,
        help="Comma-separated IPs to trust for forwarded headers (uvicorn forwarded_allow_ips).",
    ),
) -> None:
    """Run the unified gateway without auto-reload."""
    from fluxlit.runtime import load_fluxlit

    fl = load_fluxlit(target)
    run_unified(
        target,
        host=host or fl.settings.gateway_host,
        port=port or fl.settings.gateway_port,
        reload=False,
        log_level=log_level or fl.settings.log_level,
        proxy_headers=proxy_headers,
        forwarded_allow_ips=forwarded_allow_ips,
    )


@app.command()
def doctor(
    target: str = typer.Argument("app:app", help="Import path to your FluxLit instance."),
) -> None:
    """Print a quick environment and app diagnostic report."""
    import platform

    import fastapi
    import httpx
    import streamlit
    import uvicorn

    from fluxlit.runtime import load_fluxlit

    fl = load_fluxlit(target)

    typer.echo("FluxLit doctor")
    typer.echo("")
    typer.echo(f"Python: {platform.python_version()} ({platform.platform()})")
    typer.echo(f"fluxlit: {fl.__class__.__module__}")
    typer.echo(f"fastapi: {fastapi.__version__}")
    typer.echo(f"streamlit: {streamlit.__version__}")
    typer.echo(f"uvicorn: {uvicorn.__version__}")
    typer.echo(f"httpx: {httpx.__version__}")
    typer.echo("")
    typer.echo("App settings")
    typer.echo(f"- title: {fl.settings.title}")
    typer.echo(f"- api_mount_path: {fl.settings.api_mount_path}")
    typer.echo(f"- root_path: {fl.settings.root_path!r}")
    typer.echo(f"- registered pages: {len(fl.pages)}")


@app.command()
def new(name: str = typer.Argument(..., help="Project directory name.")) -> None:
    """Scaffold a minimal FluxLit application."""
    root = Path(name)
    if root.exists():
        typer.echo(f"Destination already exists: {root}", err=True)
        raise typer.Exit(code=1)
    root.mkdir(parents=True)
    (root / "app.py").write_text(
        '''"""FluxLit demo app."""

from fluxlit import FluxLit

app = FluxLit(title="FluxLit Demo")


@app.api.get("/users")
def users():
    return [{"name": "Ada"}]


@app.page("/")
def home(st, client):
    st.title("Dashboard")
    r = client.get("/users")
    st.write(r.json())


if __name__ == "__main__":
    import subprocess
    import sys

    subprocess.run([sys.executable, "-m", "fluxlit", "dev", "app:app"], check=True)
''',
        encoding="utf-8",
    )
    typer.echo(f"Created {root / 'app.py'} — run: cd {name} && fluxlit dev app:app")


def main() -> None:
    app()
