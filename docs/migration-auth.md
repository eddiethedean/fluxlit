# Migrating to JWT and OIDC

This guide assumes you already run FluxLit with public API routes under `/api` and Streamlit pages on the same origin.

## Step 1: Install the auth extra

```bash
pip install "fluxlit[auth]"
```

## Step 2: Protect a few API routes

1. Create a {class}`~fluxlit.jwt_auth.JWTAuthConfig` (HS256 for local dev, or `jwks_url` + issuer/audience for staging/prod).
2. Instantiate {class}`~fluxlit.jwt_auth.JWTBearer` once and use `Depends(bearer)` on routes.
3. Optionally wrap with {class}`~fluxlit.jwt_auth.RequireScopes` or {class}`~fluxlit.jwt_auth.RequireRoles`.

Leave health checks and static bootstrap routes open until clients are updated.

## Step 3: Streamlit calls the API with the same identity

Use {class}`~fluxlit.client.ApiClient` with:

- `auth_header_factory` reading a short-lived token from `st.session_state`, or
- `ApiClient.for_fluxlit(bearer_token=...)`, populated only after your app obtains a token **without** exposing IdP refresh tokens to the browser.

Add a small FastAPI route such as `GET /me` that returns non-sensitive claims using the same `Depends` chain as your other protected routes. Streamlit can call `/me` to drive UI without parsing JWTs manually.

## Step 4 (optional): OIDC login

1. Configure {class}`~fluxlit.oidc.GenericOIDCClient` with your issuer and call `load_discovery_sync()` at startup.
2. Build {class}`~fluxlit.oidc.OIDCBFFConfig` with a strong `first_party_secret` for HS256 access tokens issued by **your** API.
3. Call {func}`~fluxlit.oidc.register_oidc_bff_routes` on `app.api`.
4. Set `FLUXLIT_PUBLIC_BASE_URL` (or `FluxlitSettings.public_base_url`) when behind a reverse proxy so redirect URIs are correct.
5. In Streamlit, call {func}`~fluxlit.streamlit_auth.exchange_auth_code_from_query` early in the run to swap the `auth_code` query param for a bearer token.

## Step 5: Hardening

- Enable `FLUXLIT_ENABLE_SECURITY_HEADERS=1` and configure `FLUXLIT_CORS_ALLOW_ORIGINS` explicitly for browser clients.
- Run `fluxlit doctor` in CI to catch bind, env, and OAuth URL issues.

See {doc}`security` for the architecture overview and threat notes.
