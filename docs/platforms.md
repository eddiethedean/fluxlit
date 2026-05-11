# Platform recipes

FluxLit runs best when a platform gives the container one public port and lets the
process manage the Streamlit sidecar internally.

## Container hosts

Render, Fly.io, Railway-style hosts, ECS/Fargate, and similar platforms usually
need the same baseline:

- Bind the gateway to `0.0.0.0` with `FLUXLIT_GATEWAY_HOST=0.0.0.0`.
- Expose the platform-provided port as `FLUXLIT_GATEWAY_PORT` or pass `--port`.
- Run one FluxLit process per container. Scale by container/task count, not Uvicorn workers.
- Keep `.env` and secrets out of the image; inject `FLUXLIT_*`, JWT/OIDC, and app
  secrets through the platform secret manager.
- Put health checks on `/api/healthz`; use `/api/readyz` when traffic should wait
  until the Streamlit sidecar is accepting requests.

## Subpath and enterprise hosts

Platforms such as Posit Connect / Workbench, or reverse proxies that publish the
app below a prefix, need consistent public path configuration:

- Set `FLUXLIT_ROOT_PATH=/your/prefix`.
- Set `FLUXLIT_TRUST_PROXY=1` only when the front proxy is trusted.
- Tighten `FLUXLIT_FORWARDED_ALLOW_IPS` to the proxy IP/CIDR in production.
- Set `FLUXLIT_PUBLIC_BASE_URL=https://host.example/your/prefix` for OAuth redirects.

Run `fluxlit doctor` in the deployment image or shell when path, proxy, or OAuth
URLs look wrong; it checks common root path and proxy-trust mismatches.

## Multi-replica state

Each replica owns its own Streamlit sidecar and process memory. For important UI
state across refreshes, replica replacement, or non-sticky routing, pair
`fluxlit.url_session` with an external `SessionStore` such as Redis or a database.
See {doc}`url-session` for the interface and recipe.
