# Security architecture

FluxLit serves **one public origin**: the gateway forwards `/api` to FastAPI and everything else (including WebSockets) to Streamlit. Authentication must account for **two execution contexts** — API route handlers and **server-side** Streamlit code — plus whatever runs in the user’s browser.

Step-by-step recipes (JWT, OIDC BFF, Streamlit clients) live in {doc}`auth-recipes`; upgrading an existing app is covered in {doc}`migration-auth`.

## OIDC BFF: production constraints

- **Process memory only:** Login ``state`` and one-time ``auth_code`` values live in in-memory dicts on the BFF config. Use **a single API worker process** (or a single replica) unless you replace this with a shared store. Multiple Uvicorn workers or horizontally scaled replicas will see **broken or flaky logins** unless state is externalized.
- **``id_token`` validation:** When you use {class}`~fluxlit.oidc.GenericOIDCClient`, the BFF validates the IdP ``id_token`` with **JWKS** (signature, ``iss``, ``aud``, ``exp``) before minting the first-party access token. Custom :class:`~fluxlit.oidc.OIDCProvider` implementations fall back to **parse-only** ``sub`` extraction (for tests and advanced integrations); do not point untrusted providers at that path in production.

## Threat model (high level)

| Risk | Mitigation direction |
|------|---------------------|
| **XSS in Streamlit UI** | Do not store long-lived refresh tokens or IdP client secrets in `st.session_state` or display bearer tokens with `st.write`. Prefer short-lived access tokens minted by your FastAPI “BFF” and server-side `ApiClient` only. |
| **Token leakage via URL** | OAuth callbacks that put secrets in query strings can leak via Referer, logs, and shared links. FluxLit’s BFF pattern uses a **short-lived one-time `auth_code`** exchanged **server-side** over `POST /auth/exchange` before placing a bearer token in Streamlit session state. |
| **CSRF** | If you add **cookie-based** sessions, use SameSite and anti-CSRF patterns; document that Streamlit’s model is not a generic SPA. Prefer bearer tokens from server-side exchange for API calls. |
| **Spoofed forward-auth headers** | Use {class}`~fluxlit.auth.TrustedProxyUser` only when the network path guarantees clients cannot reach the app with forged `X-Remote-User`-style headers (e.g. app listens on loopback behind nginx that strips identity headers from untrusted clients). |
| **Clock skew** | JWT `exp` / `nbf` validation is sensitive to time; run NTP on production hosts. `fluxlit doctor` reminds you of this when tightening operations. |

## Where tokens should live

- **IdP client secrets:** FastAPI environment, secret manager, or deps — **never** in Streamlit subprocess env visible to untrusted code paths.
- **Access tokens for `ApiClient`:** Prefer a factory (`auth_header_factory`) or session state populated **only** after a server-side exchange; TTL should be short.
- **Internal API base:** `FLUXLIT_INTERNAL_API_BASE` points at your mounted API (e.g. `http://127.0.0.1:8000/api`). Keep it loopback or private-network in deployment guides.

## End-to-end sketch (same origin)

This ties together the gateway split: browser hits **one host**; APIs live under **`/api`**; Streamlit uses **`ApiClient`** server-side.

```python
from __future__ import annotations

import os
from typing import Annotated

from fastapi import Depends
from fluxlit import FluxLit
from fluxlit.client import ApiClient
from fluxlit.config import FluxlitSettings
from fluxlit.jwt_auth import JWTAuthConfig, JWTBearer, StandardClaims, issue_hs256_access_token
from fluxlit.streamlit_auth import bearer_headers_from_session

settings = FluxlitSettings(
    enable_security_headers=True,
    public_base_url=os.environ.get("FLUXLIT_PUBLIC_BASE_URL", "http://127.0.0.1:8000"),
)
app = FluxLit(title="Secure FluxLit", settings=settings)

# Or: _bearer = app.make_jwt_bearer() with FLUXLIT_JWT_* set on FluxlitSettings
_bearer = JWTBearer(
    JWTAuthConfig(
        issuer="https://example.internal",
        audience="example-api",
        algorithms=["HS256"],
        hs256_secret=os.environ["JWT_HS256_SECRET"],
    )
)


@app.api.get("/me")
def me(claims: Annotated[StandardClaims, Depends(_bearer)]) -> dict[str, str | None]:
    return {"sub": claims.sub}


@app.api.post("/login/dev")
def login_dev() -> dict[str, str]:
    """Replace with real OIDC / corporate IdP before production."""
    token = issue_hs256_access_token(
        subject="ada",
        issuer="https://example.internal",
        audience="example-api",
        secret=os.environ["JWT_HS256_SECRET"],
        ttl_seconds=900,
        extra_claims={"scope": "read"},
    )
    return {"access_token": token}


@app.page("/")
def home(st, client: ApiClient) -> None:
    _ = client
    if "access_token" not in st.session_state:
        st.info("POST /api/login/dev or your IdP flow, then store access_token in session.")
        return

    hdr = lambda: bearer_headers_from_session(st, session_key="access_token")
    with ApiClient(auth_header_factory=hdr) as api:
        st.write(api.get("/me").json())
```

Run with `fluxlit dev app:app`. The browser calls **`/api/me`** with `Authorization: Bearer …` only from trusted code (here, the Streamlit server via `ApiClient`), not from arbitrary browser JavaScript on the same page.

## Related topics

- {doc}`migration-auth` — incremental adoption of JWT and OIDC.
- {doc}`auth-recipes` — full examples: JWKS, OIDC BFF, forward-auth, API keys, CORS.
- {doc}`configuration` — `FLUXLIT_ENABLE_SECURITY_HEADERS`, CORS, `FLUXLIT_PUBLIC_BASE_URL`.
