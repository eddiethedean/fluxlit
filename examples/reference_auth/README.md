# Reference auth example

Minimal **FluxLit** app showing:

- HS256 JWT validation on FastAPI (`GET /api/me`)
- A **development-only** token endpoint (`POST /api/dev/login`)
- A Streamlit page: the runtime-injected `client` for `POST /dev/login`, then
  `ApiClient.for_fluxlit` + `get_model` for authenticated reads

For **production-style logging** (JSON lines, gateway access logs, upstream timeouts), see the FluxLit docs: [Observability](https://fluxlit.readthedocs.io/en/stable/observability.html) and [Configuration](https://fluxlit.readthedocs.io/en/stable/configuration.html).

**Do not** use `POST /dev/login` in production; replace it with your IdP and
`register_oidc_bff_routes` or your own OAuth flow.

## Run

From this directory:

```bash
pip install -e "../..[auth]"
fluxlit dev app:app
```

Open the app and use **Sign in (dev)**. The page uses the same internal API base URL FluxLit sets
for Streamlit (`FLUXLIT_INTERNAL_API_BASE`).

For production, replace the dev endpoint with your IdP and BFF login (`attach_oidc_login`); use
`prepare_streamlit_api_client` so the auth-code exchange talks to the API without putting tokens in
the browser query string.

## Tests

FluxLit’s main tree exercises JWT/OIDC helpers, gateway behavior, and log redaction in **`tests/`**. From the **repository root** after `pip install -e ".[dev]"`, run `python -m pytest -n auto -m "not slow"` (see **[docs/testing.md](../../docs/testing.md)**).
