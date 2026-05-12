# FluxLit documentation

**FastAPI and Streamlit on one public port.** FluxLit gives you one app object, one gateway URL, and a managed Streamlit sidecar so your API and UI deploy together.

**Install:** `pip install fluxlit` (Python **3.10+**) · **[PyPI](https://pypi.org/project/fluxlit/)** · **[GitHub](https://github.com/eddiethedean/fluxlit)**

```{tip}
New here? Follow {doc}`quickstart` first. You should have a working app at `http://127.0.0.1:8000` in a few minutes.
```

## Choose your path

| I want to… | Start here |
|------------|------------|
| Run a minimal API + Streamlit app locally | {doc}`quickstart` |
| Understand how requests reach FastAPI vs Streamlit | {doc}`architecture` |
| Configure ports, env vars, proxy paths, or reload behavior | {doc}`configuration` · {doc}`cli` |
| Deploy with containers, Kubernetes, platforms, or a reverse proxy | {doc}`deployment` · {doc}`platforms` · {doc}`production-tls` |
| Operate the app with logs, metrics, probes, and runbooks | {doc}`observability` · {doc}`runbooks` |
| Add JWT, OIDC, or call secured APIs from Streamlit | {doc}`security` · {doc}`auth-recipes` |
| Survive full page reload without cookies (URL + server store) | {doc}`url-session` |
| Deep links, query params, and invite-style URLs to Streamlit | {doc}`deep-links` |
| Call the FastAPI app from Streamlit pages (`client`, bearer, errors) | {doc}`streamlit-api-client` |
| Test API routes and Streamlit pages in Pytest | {doc}`testing` |
| Fix imports, 503 readiness, WebSockets, or wrong API paths | {doc}`troubleshooting` · `fluxlit doctor` |
| Browse API reference, support policy, or release history | {doc}`api/index` · {doc}`support-matrix` · {doc}`changelog` |

## Ideas to remember

- **Gateway:** Uvicorn serves the public URL; Streamlit runs in a child process on an internal port.
- **Routing:** `/api/*` goes to FastAPI. Everything else, including `/_stcore/...` WebSockets, is proxied to Streamlit.
- **From Streamlit, call the API** with the injected `client` using paths like `"/users"`, not `"/api/users"`. The runtime sets the base URL for you. For bearer auth, use {meth}`~fluxlit.client.ApiClient.with_bearer` or {meth}`~fluxlit.client.ApiClient.for_fluxlit`; see {doc}`streamlit-api-client` and {doc}`auth-recipes`.
- **Secured routes:** the default page `client` has **no** `Authorization` header unless you add it per request or use `with_bearer` / `for_fluxlit`.
- **Health:** `GET /api/healthz` checks the API. `GET /api/readyz` checks the Streamlit sidecar when the gateway is managing one.
- **Operations:** request IDs, structured logs, Prometheus metrics, gateway limits, graceful shutdown, and Kubernetes guidance are documented in {doc}`observability` and {doc}`deployment`.
- **Tests:** use `FluxLitTestClient` for gateway-aware API tests and `streamlit_main_path()` / AppTest for thin Streamlit smoke tests; see {doc}`testing`.

```{note}
Contributors: the default test command and CI matrix are in {doc}`testing`. Repository guidelines: {doc}`contributing`.
```

```{toctree}
---
maxdepth: 2
caption: User guide
---
quickstart
architecture
configuration
cli
deployment
platforms
production-tls
secrets
observability
rate-limiting
security
url-session
deep-links
streamlit-api-client
migration-auth
auth-recipes
troubleshooting
runbooks
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
support-matrix
roadmap
```

```{toctree}
:hidden:
genindex
```
