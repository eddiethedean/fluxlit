# Auth recipes

Short patterns linking to the Python API. Install helpers with `pip install "fluxlit[auth]"`.

## OIDC + Streamlit dashboard

1. Configure {class}`~fluxlit.oidc.GenericOIDCClient` and `load_discovery_sync()` at import/startup.
2. Call {func}`~fluxlit.oidc.register_oidc_bff_routes` on your `FluxLit.api` with {class}`~fluxlit.oidc.OIDCBFFConfig` (`first_party_secret`, `public_base_url`, paths).
3. Send users to `GET /auth/login` (under your `/api` prefix in production).
4. After redirect, call {func}`~fluxlit.streamlit_auth.exchange_auth_code_from_query` and use {class}`~fluxlit.client.ApiClient.for_fluxlit` with the stored bearer token.

## Machine client with API key

Use a FastAPI dependency that validates a shared secret header or mTLS at your edge, then issue or accept static API keys only on private networks. Call from Streamlit with `ApiClient(default_headers={"X-API-Key": ...})` — keep keys in environment or a secret backend, not in `st.session_state` long term.

## Forward-auth headers (nginx / SSO)

Use {class}`~fluxlit.auth.TrustedProxyUser` with `require_https=True` and, when applicable, `trusted_client_hosts` so only your reverse proxy can open connections. Map the same header to a user model in FastAPI and expose `GET /me` for Streamlit to mirror identity without parsing JWTs in the UI layer.

See {doc}`security` and {doc}`migration-auth` for architecture and rollout steps.
