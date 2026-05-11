# FluxLit documentation

**One port.** Your **FastAPI** routes and **Streamlit** UI share a single address—no hand-rolled reverse proxy in development, and a clear story for production.

**Install:** `pip install fluxlit` (Python **3.10+**) · **[PyPI](https://pypi.org/project/fluxlit/)** · **[GitHub](https://github.com/eddiethedean/fluxlit)**

```{tip}
New here? Follow {doc}`quickstart` end-to-end first (about five minutes). Use {doc}`troubleshooting` if the app will not start or URLs look wrong.
```

## Choose your path

| I want to… | Start here |
|------------|------------|
| Run a minimal API + Streamlit app locally | {doc}`quickstart` |
| Understand how requests reach FastAPI vs Streamlit | {doc}`architecture` |
| Set ports, env vars, or deploy behind nginx / a subpath | {doc}`configuration` |
| Use `fluxlit dev`, `fluxlit run`, reload, or Docker | {doc}`cli` · {doc}`deployment` |
| Add JWT, OIDC, or call secured APIs from Streamlit | {doc}`security` · {doc}`auth-recipes` · `pip install "fluxlit[auth]"` |
| Fix errors (imports, 503 readiness, wrong API paths) | {doc}`troubleshooting` · `fluxlit doctor` |
| Browse Python types and functions | {doc}`api/index` |

## Ideas to remember

- **Sidecar:** Streamlit runs in a **child process**. Uvicorn serves the **gateway** on the port you open in the browser.
- **Routing:** Paths under **`/api`** (default) go to FastAPI. **Everything else** (including `/_stcore/...` WebSockets) is proxied to Streamlit.
- **From Streamlit, call the API** with the injected `client` using paths like `"/users"`—**not** `"/api/users"`. The runtime sets the base URL for you.
- **Secured routes:** the default page `client` has **no** `Authorization` header. Use {meth}`~fluxlit.client.ApiClient.for_fluxlit` or the patterns in {doc}`auth-recipes`.
- **Health:** **`GET /api/healthz`** (API up). **`GET /api/readyz`** (Streamlit sidecar reachable when using `fluxlit dev` / `fluxlit run`). Details: {doc}`deployment`, {doc}`observability`.

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
observability
rate-limiting
security
migration-auth
auth-recipes
troubleshooting
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
