from __future__ import annotations

from pathlib import Path

import typer

from fluxlit.runtime import run_unified

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command()
def dev(
    target: str = typer.Argument("app:app", help="Import path to your FluxLit instance."),
    host: str = typer.Option("127.0.0.1", help="Bind address for the unified gateway."),
    port: int = typer.Option(8000, help="Port for the unified gateway."),
    reload: bool = typer.Option(
        False,
        help="Reload the API gateway on code changes (experimental).",
    ),
) -> None:
    """Run FastAPI + Streamlit behind a single ASGI gateway (development)."""
    run_unified(target, host=host, port=port, reload=reload)


@app.command("run")
def run_cmd(
    target: str = typer.Argument("app:app", help="Import path to your FluxLit instance."),
    host: str = typer.Option("127.0.0.1", help="Bind address for the unified gateway."),
    port: int = typer.Option(8000, help="Port for the unified gateway."),
) -> None:
    """Run the unified gateway without auto-reload."""
    run_unified(target, host=host, port=port, reload=False)


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
