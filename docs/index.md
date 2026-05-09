# FluxLit

Production-oriented unified runtime for **FastAPI** and **Streamlit**: one public port, one CLI, and a single **FluxLit** app object for HTTP APIs plus Streamlit UI pages.

**[PyPI](https://pypi.org/project/fluxlit/)** · **[GitHub](https://github.com/eddiethedean/fluxlit)**

## At a glance

- **Sidecar model:** Streamlit runs in a subprocess; a Starlette ASGI **gateway** (Uvicorn) serves one public port.
- **Routing:** paths under `/api` (configurable) go to FastAPI; everything else is proxied to Streamlit, including WebSockets.
- **Streamlit to API:** page handlers receive a server-side {class}`~fluxlit.client.ApiClient` (base URL includes `/api`). It does **not** send bearer tokens by default; use {meth}`~fluxlit.client.ApiClient.for_fluxlit` or an `auth_header_factory` for protected routes, or {func}`~fluxlit.streamlit_auth.prepare_streamlit_api_client` after OIDC (requires `pip install "fluxlit[auth]"`).
- **Developer workflow:** `fluxlit dev`, `fluxlit run`, project file (`fluxlit.toml` / `[tool.fluxlit]`), `fluxlit doctor`, `fluxlit build`.

Python **3.10+** required. Install: `pip install fluxlit`. For JWT/OIDC/BFF patterns: `pip install "fluxlit[auth]"` and start with {doc}`auth-recipes`.

```{toctree}
---
maxdepth: 2
caption: User guide
---
quickstart
architecture
configuration
security
migration-auth
auth-recipes
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
