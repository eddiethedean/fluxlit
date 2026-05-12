# Migrating to JWT and OIDC

This guide assumes you already run FluxLit with public API routes under **`/api`** and Streamlit on the same origin.

## Step 1: Install the auth extra

```bash
pip install "fluxlit[auth]"
```

## Step 2: Protect a few API routes

### 2a. Shared JWT dependency (friendly: env + `make_jwt_bearer`)

If you set `FLUXLIT_JWT_ISSUER`, `FLUXLIT_JWT_AUDIENCE`, and `FLUXLIT_JWT_HS256_SECRET` (or `FLUXLIT_JWT_JWKS_URL`), you can skip hand-building {class}`~fluxlit.auth.jwt.JWTAuthConfig`:

```python
from fluxlit import FluxLit

app = FluxLit()
_bearer = app.make_jwt_bearer()
```

### 2a-alt. Shared JWT dependency (explicit config)

Create one {class}`~fluxlit.auth.jwt.JWTBearer` and reuse it. HS256 is fine for local development; use `jwks_url` + RS256 for staging/production.

```python
# app.py (fragment)
import os
from fluxlit.auth.jwt import JWTAuthConfig, JWTBearer

_bearer = JWTBearer(
    JWTAuthConfig(
        issuer=os.environ["JWT_ISSUER"],
        audience=os.environ["JWT_AUDIENCE"],
        algorithms=["HS256"],
        hs256_secret=os.environ["JWT_HS256_SECRET"],
    )
)
```

### 2b. Attach to routes

```python
from typing import Annotated

from fastapi import Depends
from fluxlit import FluxLit
from fluxlit.auth.jwt import StandardClaims

app = FluxLit(title="My app")


@app.api.get("/me")
def me(claims: Annotated[StandardClaims, Depends(_bearer)]):
    return {"sub": claims.sub}


@app.api.get("/healthz")  # already registered by FluxLit on the inner API
def _note() -> None:
    """Use the built-in health route or add public routes without Depends(_bearer)."""
```

### 2c. Optional: scopes / roles

```python
from fluxlit.auth.jwt import RequireScopes

_need_read = RequireScopes(_bearer, "data.read")


@app.api.get("/v1/widgets")
def list_widgets(_: Annotated[StandardClaims, Depends(_need_read)]):
    return []
```

Leave public bootstrap routes untouched until all callers send a bearer token.

## Step 3: Streamlit calls the API with the same identity

### 3a. Identity endpoint

Expose **`GET /me`** (or similar) using the **same** `Depends(_bearer)` as your other protected APIs. Streamlit uses it to drive UI labels without parsing JWTs.

### 3b. ApiClient with a token from session

**One call:** {func}`fluxlit.streamlit_auth.prepare_streamlit_api_client` runs the BFF `auth_code` exchange when the URL contains it, then returns an {class}`~fluxlit.client.ApiClient` that already sends `Authorization: Bearer …` if a token is in `st.session_state` (default key `fluxlit_access_token`).

```python
from fluxlit.client import ApiClient
from fluxlit.streamlit_auth import prepare_streamlit_api_client


@app.page("/")
def home(st, client: ApiClient) -> None:
    _ = client
    api = prepare_streamlit_api_client(st)
    r = api.get("/me")
    if r.status_code == 401:
        st.warning("Sign in (e.g. open /api/auth/login).")
        return
    st.write("Hello,", r.json().get("sub"))
```

**Manual:** after login or token exchange, store only a **short-lived** access token in `st.session_state` and bind headers per request:

```python
from fluxlit.client import ApiClient
from fluxlit.streamlit_auth import bearer_headers_from_session


@app.page("/alt")
def home_alt(st, client: ApiClient) -> None:
    _ = client
    if "access_token" not in st.session_state:
        st.warning("Not signed in.")
        return

    def hdr() -> dict[str, str]:
        return bearer_headers_from_session(st, session_key="access_token")

    with ApiClient(auth_header_factory=hdr) as api:
        profile = api.get("/me").json()
    st.write("Hello,", profile.get("sub"))
```

### 3c. Correlation IDs (optional)

If you run code in a context where {func}`fluxlit.logging.context.set_request_id` is active, enable:

```python
ApiClient(propagate_request_id=True)
```

so internal calls forward `X-Request-ID`. In a plain Streamlit script this is usually unset.

## Step 4 (optional): OIDC login

### 4a. Discovery and BFF registration

**Shorter:** use {meth}`fluxlit.app.FluxLit.attach_oidc_login` so `public_base_url` and `first_party_secret` default from settings (`FLUXLIT_PUBLIC_BASE_URL`, `FLUXLIT_OIDC_BFF_SECRET`):

```python
import os

from fluxlit import FluxLit
from fluxlit.config import FluxlitSettings
from fluxlit.oidc import GenericOIDCClient, GenericOIDCClientConfig

settings = FluxlitSettings()
app = FluxLit(title="OIDC", settings=settings)

oidc = GenericOIDCClient(
    GenericOIDCClientConfig(
        issuer=os.environ["OIDC_ISSUER"],
        client_id=os.environ["OIDC_CLIENT_ID"],
        client_secret=os.environ["OIDC_CLIENT_SECRET"],
    )
)
oidc.load_discovery_sync()
app.attach_oidc_login(oidc)
```

**Manual:** same as above but call {func}`fluxlit.oidc.register_oidc_bff_routes` yourself with {class}`~fluxlit.oidc.OIDCBFFConfig` if you need full control.

Register the **callback URL** with your IdP:  
`{FLUXLIT_PUBLIC_BASE_URL}/api/auth/callback` (default callback path; adjust if you change `callback_path`).

### 4b. Streamlit: exchange `auth_code`

At the top of your main page:

```python
from fluxlit.streamlit_auth import exchange_auth_code_from_query


@app.page("/")
def home(st, client: ApiClient) -> None:
    exchange_auth_code_from_query(st, client, exchange_path="/auth/exchange")
    ...
```

This performs a **server-side** `POST` to `/api/auth/exchange` and stores `fluxlit_access_token`. Use that token with `ApiClient.for_fluxlit` or `bearer_headers_from_session` when calling APIs that expect your BFF-issued JWT (configure {class}`~fluxlit.auth.jwt.JWTBearer` with the same issuer/audience/secret as `OIDCBFFConfig`).

## Step 5: Hardening

**Environment / settings**

```bash
export FLUXLIT_ENABLE_SECURITY_HEADERS=1
export FLUXLIT_CORS_ALLOW_ORIGINS='["https://trusted-ui.example.com"]'
export FLUXLIT_PUBLIC_BASE_URL=https://app.example.com
```

**Doctor (CI or pre-deploy)**

```bash
fluxlit doctor app:app
```

See {doc}`security` for threats and token placement, {doc}`secrets` for rotation and avoiding leaks in logs, {doc}`production-tls` for proxies and TLS, and {doc}`auth-recipes` for copy-paste examples (forward-auth, API keys, JWKS).

## FluxLit 0.8.1 (auth and internal client)

- **OIDC BFF (custom provider):** If you call {func}`fluxlit.oidc.register_oidc_bff_routes` with a custom {class}`~fluxlit.oidc.OIDCProvider` (anything other than {class}`~fluxlit.oidc.GenericOIDCClient`), set ``OIDCBFFConfig.allow_unverified_id_token_for_custom_oidc=True`` only when that provider already verified ``id_token`` or for tests. Prefer ``GenericOIDCClient`` in production so the BFF validates with JWKS.
- **`ApiClient`:** Paths passed to ``get`` / ``post`` / ``request`` must be **relative** to the API base; absolute or scheme-relative URL strings raise ``ValueError``.
- **`public_base_url`:** Leave unset only for local experiments; production should set ``FLUXLIT_PUBLIC_BASE_URL`` (or ``OIDCBFFConfig.public_base_url``) so OAuth redirect URIs are stable behind proxies. An empty value now triggers a ``UserWarning`` when routes are registered.
