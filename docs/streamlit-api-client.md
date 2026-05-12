# Streamlit → FastAPI: `ApiClient` patterns

**Why read this:** pick the right client for each Streamlit page, attach bearer tokens safely, handle `httpx` errors consistently, and confirm the **same internal API base** is used for public and authenticated calls (including subpaths / `FLUXLIT_ROOT_PATH`).

## Which client?

| Entry point | When to use it |
|-------------|----------------|
| **Injected `client`** (`PageFn`) | Default for **public** routes: `client.get("/items")`. Same `FLUXLIT_INTERNAL_API_BASE` as the rest of the stack. **No `Authorization` header** unless you add one per call or upgrade the client (below). |
| {meth}`~fluxlit.client.ApiClient.with_bearer` | Same base URL and options as the injected client, plus a static **Bearer** token (for example from `st.session_state` after login). Prefer when you already hold the page `client` and only need to add auth. |
| {meth}`~fluxlit.client.ApiClient.for_fluxlit` | **New** client from scratch with `bearer_token=` or `auth_header_factory=` (refresh flows, OIDC helpers in {doc}`auth-recipes`). Use when you are not using the injected instance or need a factory. |

All of these resolve paths **relative to the API mount** (for example `"/users"`, not `"/api/users"`). The parent process sets **`FLUXLIT_INTERNAL_API_BASE`** (including the `/api` suffix) for Streamlit subprocesses, so **injected `client`**, **`client.with_bearer(...)`**, and **`ApiClient.for_fluxlit(...)`** share that base when you do not override `base_url`.

## Public, authenticated, and admin-style calls

**Public**

```python
from typing import Any

from fluxlit.client import ApiClient

def home(st: Any, client: ApiClient, /) -> None:
    r = client.get("/healthz")
    r.raise_for_status()
```

**Authenticated (Bearer in session)**

```python
from typing import Any

from fluxlit.client import ApiClient

def dashboard(st: Any, client: ApiClient, /) -> None:
    token = st.session_state.get("access_token")
    if not token:
        st.warning("Sign in first.")
        return
    with client.with_bearer(token) as api:
        r = api.get("/users/me")
        r.raise_for_status()
        st.json(r.json())
```

**Authenticated (standalone client)**

```python
with ApiClient.for_fluxlit(bearer_token=st.session_state["access_token"]) as api:
    user = api.get_model("/users/me", MyUserModel)
```

**Admin vs normal users** is enforced on the **FastAPI** side (dependencies, roles). The Streamlit client does not change shape; only **headers** and **which routes** you call differ.

## Bearer tokens and secrets

- Prefer **`auth_header_factory`** (or {doc}`auth-recipes` helpers) when the token is short-lived and should be read **at request time** rather than captured once from widget state.
- Never log raw tokens. On failures, log status codes and safe `detail` keys only.

## Errors (`httpx`)

Use the same patterns as any `httpx` app: distinguish transport failures from HTTP error statuses.

```python
import httpx

try:
    r = client.get("/items/1")
    r.raise_for_status()
except httpx.HTTPStatusError as e:
    st.error(f"API error {e.response.status_code}")
except httpx.RequestError as e:
    st.error(f"Could not reach API: {e.__class__.__name__}")
```

For Pydantic helpers, {meth}`~fluxlit.client.ApiClient.get_model` / {meth}`~fluxlit.client.ApiClient.post_model` call `raise_for_status()` before parsing.

## Request IDs

The injected client comes from {meth}`fluxlit.app.FluxLit.get_client`, which enables **request ID propagation** when {attr}`~fluxlit.config.FluxlitSettings.debug` is on (see {doc}`configuration` / {doc}`observability`). {meth}`~fluxlit.client.ApiClient.with_bearer` copies that flag; {meth}`~fluxlit.client.ApiClient.for_fluxlit` takes `propagate_request_id=` explicitly.

## Tests

Use {class}`~fluxlit.testing.FluxLitTestClient` for gateway-aware API tests, then keep Streamlit smoke tests thin. See {doc}`testing` (Bearer section).

## See also

- {doc}`streamlit-pages-typing` — typed page handlers, ``Depends``, query models
- {doc}`troubleshooting` — wrong paths, `FLUXLIT_INTERNAL_API_BASE`, proxy prefixes
- {doc}`auth-recipes` — OIDC BFF, refresh, `prepare_streamlit_api_client`
- {doc}`url-session-token-security` — query tokens, email links, and logging
- {class}`~fluxlit.client.ApiClient` — API reference
