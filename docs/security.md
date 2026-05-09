# Security architecture

FluxLit serves **one public origin**: the gateway forwards `/api` to FastAPI and everything else (including WebSockets) to Streamlit. Authentication must account for **two execution contexts** — API route handlers and **server-side** Streamlit code — plus whatever runs in the user’s browser.

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

## Related topics

- {doc}`migration-auth` — incremental adoption of JWT and OIDC.
- {doc}`auth-recipes` — OIDC, API keys, forward-auth patterns.
- {doc}`configuration` — `FLUXLIT_ENABLE_SECURITY_HEADERS`, CORS, `FLUXLIT_PUBLIC_BASE_URL`.
