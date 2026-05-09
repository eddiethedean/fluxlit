# Reference auth example

Minimal **FluxLit** app showing:

- HS256 JWT validation on FastAPI (`GET /api/me`)
- A **development-only** token endpoint (`POST /api/dev/login`)
- A Streamlit page that calls the API with the same bearer token via `ApiClient.for_fluxlit`

**Do not** use `POST /dev/login` in production; replace it with your IdP and
`register_oidc_bff_routes` or your own OAuth flow.

## Run

From this directory:

```bash
pip install -e "../..[auth]"
fluxlit dev app:app
```

Obtain a token:

```bash
curl -s -X POST http://127.0.0.1:8000/api/dev/login | jq .
```

Paste the `access_token` into the Streamlit sidebar field, or set session state programmatically in a real app.
