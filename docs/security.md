# Security architecture

**Read this before** putting real user data behind FluxLit: how the gateway splits API vs UI, where tokens should live, and how to avoid common leaks (XSS, Referer, forward-auth).

FluxLit serves **one public origin**: the gateway forwards `/api` to FastAPI and everything else (including WebSockets) to Streamlit. Authentication must account for **two execution contexts** — API route handlers and **server-side** Streamlit code — plus whatever runs in the user’s browser.

Step-by-step recipes (JWT, OIDC BFF, Streamlit clients) live in {doc}`auth-recipes`; upgrading an existing app is covered in {doc}`migration-auth`.

## OIDC BFF: production constraints

- **Process memory only:** Login ``state`` and one-time ``auth_code`` values live in in-memory dicts on the BFF config. Use **a single API worker process** (or a single replica) unless you replace this with a shared store. Multiple Uvicorn workers or horizontally scaled replicas will see **broken or flaky logins** unless state is externalized.
- **``id_token`` validation:** When you use {class}`~fluxlit.auth.oidc.GenericOIDCClient`, the BFF validates the IdP ``id_token`` with **JWKS** (signature, ``iss``, ``aud``, ``exp``) before minting the first-party access token. For a **custom** :class:`~fluxlit.auth.oidc.OIDCProvider`, parse-only ``sub`` extraction is **disabled by default**; set ``OIDCBFFConfig.allow_unverified_id_token_for_custom_oidc=True`` only when your provider already verified the token or for controlled tests (see {doc}`security`).

## Threat model (high level)

| Risk | Mitigation direction |
|------|---------------------|
| **XSS in Streamlit UI** | Do not store long-lived refresh tokens or IdP client secrets in `st.session_state` or display bearer tokens with `st.write`. Prefer short-lived access tokens minted by your FastAPI “BFF” and server-side `ApiClient` only. |
| **Token leakage via URL** | OAuth callbacks that put secrets in query strings can leak via Referer, logs, and shared links. FluxLit’s BFF pattern uses a **short-lived one-time `auth_code`** exchanged **server-side** over `POST /auth/exchange` before placing a bearer token in Streamlit session state. For URL-session ids, invite links, and logging expectations, see {doc}`url-session-token-security`. |
| **CSRF** | If you add **cookie-based** sessions, use SameSite and anti-CSRF patterns; document that Streamlit’s model is not a generic SPA. Prefer bearer tokens from server-side exchange for API calls. |
| **Spoofed forward-auth headers** | Use {class}`~fluxlit.auth.TrustedProxyUser` only when the network path guarantees clients cannot reach the app with forged `X-Remote-User`-style headers (e.g. app listens on loopback behind nginx that strips identity headers from untrusted clients). |
| **Clock skew** | JWT `exp` / `nbf` validation is sensitive to time; run NTP on production hosts. `fluxlit doctor` reminds you of this when tightening operations. |
| **Credential leakage via header forwarding** | ``FLUXLIT_GATEWAY_FORWARD_CLIENT_HEADERS_TO_STREAMLIT`` / :attr:`~fluxlit.config.FluxlitSettings.gateway_forward_client_headers_to_streamlit` defaults to **empty**. When **non-empty**, FluxLit **merges** those header **names** from the raw browser scope onto the gateway → Streamlit **HTTP** ``httpx`` hop; **Authorization**, **Cookie**, and hop-by-hop names are **rejected from the allowlist** itself. **Separately**, the HTTP proxy already forwards **most** other client headers that survive :func:`~fluxlit.gateway.header_filter.filter_request_headers` (cookies and auth headers are **not** stripped by FluxLit at the wire). What appears in ``st.context.headers`` depends on Streamlit. Misconfiguration can still expose PII in logs; prefer {func}`~fluxlit.pages.di.set_page_header_context` after validating a trusted proxy path. See the subsection below, {doc}`configuration`, and {doc}`cookbook`. **WebSockets** do not use this allowlist — see :mod:`fluxlit.gateway.websocket_proxy`. |

## Gateway → Streamlit: HTTP vs WebSocket headers

### HTTP proxy hop

1. **Baseline:** For each request, upstream headers are seeded from the client scope after :func:`fluxlit.gateway.header_filter.filter_request_headers` (drops hop-by-hop headers, client ``Host``, and client ``X-Forwarded-*``). **Most other client header lines are copied** — including typical ``Cookie`` and ``Authorization`` values — before FluxLit applies synthetic ``Host``, trusted ``X-Forwarded-*`` / prefix lines, and ``X-Request-ID``.
2. **Optional allowlist (0.10+):** ``FLUXLIT_GATEWAY_FORWARD_CLIENT_HEADERS_TO_STREAMLIT`` **merges** allowlisted names from the **raw** browser scope onto that header map. It **does not remove** headers that were already copied in step 1. An **empty** list means “skip this merge”; it does **not** disable cookie or bearer forwarding at the wire. Names like ``authorization`` and ``cookie`` cannot appear in the allowlist.
3. **Script visibility:** ``st.context.headers`` and :class:`~fluxlit.pages.di.Header` read what Streamlit exposes; that may differ from the full upstream request.

### WebSocket proxy

The allowlist **does not apply**. :mod:`fluxlit.gateway.websocket_proxy` forwards most browser handshake headers to the Streamlit upstream, except a fixed denylist (notably ``Sec-WebSocket-Extensions`` is dropped so the gateway’s own compression negotiation does not break the upstream handshake).

### Guidance

- **Threats:** header smuggling, accidental logging of sensitive values, cache poisoning if names overlap with cache semantics — treat the allowlist like firewall policy even though it only **adds** lines.
- **Recommendation:** keep allowlists minimal; validate edge trust (``FLUXLIT_FORWARDED_ALLOW_IPS``, ``trust_proxy``) per {doc}`production-tls`; use {func}`~fluxlit.pages.di.set_page_header_context` when you need explicit, validated injection for typed pages.

## Where tokens should live

- **IdP client secrets:** FastAPI environment, secret manager, or deps — **never** in Streamlit subprocess env visible to untrusted code paths.
- **Access tokens for `ApiClient`:** Prefer a factory (`auth_header_factory`) or session state populated **only** after a server-side exchange; TTL should be short.
- **Internal API base:** `FLUXLIT_INTERNAL_API_BASE` points at your mounted API (e.g. `http://127.0.0.1:8000/api`). Keep it loopback or private-network in deployment guides. Server-side :class:`~fluxlit.client.ApiClient` rejects absolute and scheme-relative ``path`` arguments so ``httpx`` cannot be tricked into calling arbitrary hosts.

## End-to-end sketch (same origin)

This ties together the gateway split: browser hits **one host**; APIs live under **`/api`**; Streamlit uses **`ApiClient`** server-side.

```python
from __future__ import annotations

import os
from typing import Annotated, Any

from fastapi import Depends
from fluxlit import FluxLit, bearer_headers_from_session
from fluxlit.client import ApiClient
from fluxlit.config import FluxlitSettings
from fluxlit.auth.jwt import JWTAuthConfig, JWTBearer, StandardClaims, issue_hs256_access_token

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
def home(st: Any, client: ApiClient) -> None:
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

- {doc}`secrets` — logs, secret stores, JWT/OIDC rotation runbook.
- {doc}`production-tls` — HSTS, proxy trust, CSP notes, TLS validation.
- {doc}`migration-auth` — incremental adoption of JWT and OIDC.
- {doc}`auth-recipes` — full examples: JWKS, OIDC BFF, forward-auth, API keys, CORS.
- {doc}`configuration` — `FLUXLIT_ENABLE_SECURITY_HEADERS`, CORS, `FLUXLIT_PUBLIC_BASE_URL`, `FLUXLIT_GATEWAY_FORWARD_CLIENT_HEADERS_TO_STREAMLIT`.
