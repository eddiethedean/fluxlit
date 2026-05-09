# Auth recipes

Concrete patterns for securing **FastAPI** (`FluxLit.api`) and calling it from **Streamlit** with {class}`~fluxlit.client.ApiClient`. Install JWT/OIDC helpers:

```bash
pip install "fluxlit[auth]"
```

For a **minimal end-to-end** demo (dev HS256, `ApiClient.for_fluxlit`, `get_model`), clone the repo and run `examples/reference_auth/` with `fluxlit dev app:app`.

Public URLs below assume the default API mount **`/api`** (see {attr}`~fluxlit.config.FluxlitSettings.api_mount_path`). Routes you add on `app.api` appear under that prefix in the browser (for example `/me` → `https://your-host/api/me`).

## Friendly API (env-driven, less boilerplate)

**JWT:** set `FLUXLIT_JWT_ISSUER`, `FLUXLIT_JWT_AUDIENCE`, and either `FLUXLIT_JWT_HS256_SECRET` or `FLUXLIT_JWT_JWKS_URL`, then use `app.make_jwt_bearer()` anywhere you would build {class}`~fluxlit.jwt_auth.JWTBearer` by hand.

```python
from typing import Annotated

from fastapi import Depends
from fluxlit import FluxLit
from fluxlit.jwt_auth import StandardClaims

app = FluxLit()  # loads FluxlitSettings from env / .env
_bearer = app.make_jwt_bearer()


@app.api.get("/me")
def me(claims: Annotated[StandardClaims, Depends(_bearer)]):
    return {"sub": claims.sub}
```

**OIDC login:** configure a {class}`~fluxlit.oidc.GenericOIDCClient`, call `load_discovery_sync()`, then one line on your `FluxLit` instance (uses `FLUXLIT_PUBLIC_BASE_URL` and `FLUXLIT_OIDC_BFF_SECRET` by default):

```python
import os
from fluxlit import FluxLit
from fluxlit.config import FluxlitSettings
from fluxlit.oidc import GenericOIDCClient, GenericOIDCClientConfig

settings = FluxlitSettings()  # FLUXLIT_PUBLIC_BASE_URL, FLUXLIT_OIDC_BFF_SECRET, …
app = FluxLit(settings=settings)

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

**Streamlit:** one client for both the auth-code exchange and authenticated API calls:

```python
from fluxlit import prepare_streamlit_api_client

@app.page("/")
def home(st, client):
    _ = client
    api = prepare_streamlit_api_client(st)
    r = api.get("/me")
    ...
```

---

## JWT: protect routes (development HS256)

Use a long random secret (32+ bytes) from the environment — never commit it.

```python
from __future__ import annotations

import os
from typing import Annotated

from fastapi import Depends
from fluxlit import FluxLit
from fluxlit.jwt_auth import JWTAuthConfig, JWTBearer, StandardClaims, issue_hs256_access_token

JWT_SECRET = os.environ["FLUXLIT_JWT_HS256_SECRET"]  # e.g. openssl rand -hex 32
JWT_ISSUER = "https://mycompany.internal/auth"
JWT_AUDIENCE = "fluxlit-demo-api"

_bearer = JWTBearer(
    JWTAuthConfig(
        issuer=JWT_ISSUER,
        audience=JWT_AUDIENCE,
        algorithms=["HS256"],
        hs256_secret=JWT_SECRET,
    )
)

app = FluxLit(title="Secure demo")


@app.api.get("/me")
def me(claims: Annotated[StandardClaims, Depends(_bearer)]) -> dict[str, str | None]:
    """Same claims object you can mirror from Streamlit via this endpoint."""
    return {"sub": claims.sub, "scope": claims.scope}


@app.api.post("/dev/issue-token")
def dev_issue_token() -> dict[str, str]:
    """Development only — replace with real login / OIDC in production."""
    token = issue_hs256_access_token(
        subject="user-123",
        issuer=JWT_ISSUER,
        audience=JWT_AUDIENCE,
        secret=JWT_SECRET,
        ttl_seconds=900,
        extra_claims={"scope": "read write"},
    )
    return {"access_token": token, "token_type": "bearer"}
```

---

## JWT: production-style RS256 + JWKS

Point `jwks_url` at your IdP’s JWKS document. PyJWT will fetch keys and respect `kid` rotation.

```python
import os

from fluxlit.jwt_auth import JWTAuthConfig, JWTBearer

_bearer_prod = JWTBearer(
    JWTAuthConfig(
        issuer=os.environ["JWT_ISSUER"],  # e.g. https://login.microsoftonline.com/{tid}/v2.0
        audience=os.environ["JWT_AUDIENCE"],
        algorithms=["RS256"],
        jwks_url=os.environ["JWT_JWKS_URI"],
        leeway_seconds=10,
    )
)
```

Use `Depends(_bearer_prod)` on routes the same way as the HS256 example.

---

## Scopes and roles

```python
from fluxlit.jwt_auth import RequireScopes, RequireRoles

_need_reports = RequireScopes(_bearer, "reports.read", scope_claim="scope")
_need_admin = RequireRoles(_bearer, "admin", roles_claim="roles")


@app.api.get("/reports/summary")
def reports_summary(claims: Annotated[StandardClaims, Depends(_need_reports)]):
    return {"viewer": claims.sub}


@app.api.post("/admin/purge")
def admin_purge(claims: Annotated[StandardClaims, Depends(_need_admin)]):
    return {"by": claims.sub}
```

---

## Streamlit: call the API with a bearer token

Prefer **server-side** headers — do not paste tokens into `st.text_input` in production.

```python
from fluxlit.client import ApiClient
from fluxlit.streamlit_auth import bearer_headers_from_session


@app.page("/dashboard")
def dashboard(st, client: ApiClient) -> None:
    _ = client  # default client is unauthenticated
    token = st.session_state.get("access_token")
    if not token:
        st.info("Open /api/auth/login (or your login flow) first.")
        return

    def headers() -> dict[str, str]:
        return bearer_headers_from_session(st, session_key="access_token")

    with ApiClient(auth_header_factory=headers) as api:
        r = api.get("/me")
        if r.status_code != 200:
            st.error(r.text)
            return
        st.json(r.json())
```

Shorter variant when you already hold the token string:

```python
with ApiClient.for_fluxlit(bearer_token=st.session_state["access_token"]) as api:
    st.write(api.get("/me").json())
```

---

## OIDC login + BFF (`auth_code` exchange)

Wire discovery, register routes on **`app.api`**, set a public base URL behind proxies, then consume the one-time code in Streamlit.

```python
import os

from fluxlit import FluxLit
from fluxlit.client import ApiClient
from fluxlit.config import FluxlitSettings
from fluxlit.oidc import (
    GenericOIDCClient,
    GenericOIDCClientConfig,
    OIDCBFFConfig,
    register_oidc_bff_routes,
)
from fluxlit.streamlit_auth import exchange_auth_code_from_query

oidc = GenericOIDCClient(
    GenericOIDCClientConfig(
        issuer=os.environ["OIDC_ISSUER"].rstrip("/"),
        client_id=os.environ["OIDC_CLIENT_ID"],
        client_secret=os.environ["OIDC_CLIENT_SECRET"],
    )
)
oidc.load_discovery_sync()

app = FluxLit(
    title="OIDC demo",
    settings=FluxlitSettings(
        public_base_url=os.environ.get("FLUXLIT_PUBLIC_BASE_URL", "http://127.0.0.1:8000"),
        enable_security_headers=True,
    ),
)

register_oidc_bff_routes(
    app.api,
    OIDCBFFConfig(
        oidc=oidc,
        first_party_secret=os.environ["BFF_FIRST_PARTY_JWT_SECRET"],
        token_issuer="my-bff",
        token_audience="my-streamlit-app",
        access_token_ttl_seconds=3600,
        public_base_url=app.settings.public_base_url,
    ),
)


@app.page("/")
def home(st, client: ApiClient) -> None:
    # Swap ?auth_code=... for a bearer token (server-side POST /api/auth/exchange)
    exchange_auth_code_from_query(st, client, exchange_path="/auth/exchange")
    if "fluxlit_access_token" not in st.session_state:
        st.markdown("Sign in: open **`/api/auth/login`** on this host.")
        return
    st.success("Authenticated — token stored server-side in session_state.")
```

Browser flow:

1. Visit `GET /api/auth/login` → redirect to IdP.
2. IdP redirects to `GET /api/auth/callback` → redirect to `/?auth_code=...`.
3. Streamlit runs `exchange_auth_code_from_query` → `POST /api/auth/exchange` → stores `fluxlit_access_token`.

---

## Forward-auth (reverse proxy / SSO)

Use only when the app **cannot** be reached with forged identity headers (bind to loopback, or restrict `trusted_client_hosts` to your proxy).

```python
from fastapi import Depends
from fluxlit import FluxLit
from fluxlit.auth import TrustedProxyUser, TrustedProxyUserConfig

# Upstream addresses allowed to open TCP to your app (TestClient uses "testclient")
TRUSTED_PROXIES = frozenset({"127.0.0.1", "testclient"})

_remote_user = TrustedProxyUser(
    TrustedProxyUserConfig(
        header_name="X-Remote-User",
        require_https=True,
        trusted_client_hosts=TRUSTED_PROXIES,
    )
)

app = FluxLit(title="Behind nginx")


@app.api.get("/me")
def me(username: str = Depends(_remote_user)) -> dict[str, str]:
    return {"user": username}
```

Example nginx snippet (conceptual):

```nginx
proxy_set_header X-Remote-User $upstream_http_remote_user;
proxy_set_header X-Forwarded-Proto $scheme;
```

---

## API key for automation (header dependency)

```python
import os

from fastapi import Depends, Header, HTTPException, status

async def require_service_api_key(x_api_key: str | None = Header(default=None)) -> str:
    expected = os.environ.get("FLUXLIT_SERVICE_API_KEY", "")
    if not expected or x_api_key != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return x_api_key


app = FluxLit(title="Internal tools")


@app.api.get("/etl/status")
def etl_status(_: str = Depends(require_service_api_key)) -> dict[str, str]:
    return {"status": "idle"}
```

From Streamlit (key from env in the Streamlit process, not from user input):

```python
import os

from fluxlit.client import ApiClient

with ApiClient(
    default_headers={"X-API-Key": os.environ["FLUXLIT_SERVICE_API_KEY"]},
) as api:
    st.write(api.get("/etl/status").json())
```

---

## CORS and security headers (settings)

```python
from fluxlit import FluxLit
from fluxlit.config import FluxlitSettings

settings = FluxlitSettings(
    enable_security_headers=True,
    cors_allow_origins=["https://analytics.mycompany.com"],
    cors_allow_credentials=True,
    public_base_url="https://app.mycompany.com",
)
app = FluxLit(title="Production layout", settings=settings)
```

Equivalent environment variables: `FLUXLIT_ENABLE_SECURITY_HEADERS`, `FLUXLIT_CORS_ALLOW_ORIGINS` (JSON array), `FLUXLIT_PUBLIC_BASE_URL`. See {doc}`configuration`.

---

See {doc}`security` for the threat model and {doc}`migration-auth` for a phased rollout.
