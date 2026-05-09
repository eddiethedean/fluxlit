# FluxLit

Production-oriented unified runtime for **FastAPI** and **Streamlit**: one public port, one CLI, and a single **FluxLit** app object for HTTP APIs plus Streamlit UI pages.

**[PyPI](https://pypi.org/project/fluxlit/)** · **[GitHub](https://github.com/eddiethedean/fluxlit)**

## At a glance

- **Sidecar model:** Streamlit runs in a subprocess; a Starlette ASGI **gateway** (Uvicorn) serves one public port.
- **Routing:** paths under `/api` (configurable) go to FastAPI; everything else is proxied to Streamlit, including WebSockets.
- **Developer workflow:** `fluxlit dev`, `fluxlit run`, project file (`fluxlit.toml` / `[tool.fluxlit]`), `fluxlit doctor`, `fluxlit build`.

Python **3.10+** required. Install: `pip install fluxlit`.

```{toctree}
---
maxdepth: 2
caption: User guide
---
quickstart
architecture
configuration
cli
testing
contributing
```

```{toctree}
---
maxdepth: 2
caption: Reference
---
api/index
changelog
roadmap
```

```{toctree}
:hidden:
genindex
```
