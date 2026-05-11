# Rate limiting

FluxLit exposes **one public port**: the gateway sends `/api/...` to FastAPI and everything else to Streamlit. Rate limits should usually target **`/api/*`** first (machine clients, abusive API traffic) while leaving Streamlit’s HTML/WebSocket paths usable for legitimate UI sessions.

## Starlette / FastAPI middleware

Mount middleware on `FluxLit.api` (the inner FastAPI app), for example a simple in-memory sliding window or a shared Redis backend:

```python
from fluxlit import FluxLit

app = FluxLit(title="Rated")

@app.api.middleware("http")
async def rate_limit(request, call_next):
    if request.url.path.startswith(app.settings.api_mount_path):
        ...  # enforce limit by client IP or API key
    return await call_next(request)
```

## slowapi (FastAPI community pattern)

The **`slowapi`** library integrates with Starlette/FastAPI and can key limits by IP or custom values. Apply decorators to routes on `app.api`, or use a global limiter wired in `FastAPI` state. Keep limits **stricter** on expensive endpoints (login, token exchange, exports).

## Reverse proxy

For production, many teams prefer **nginx**, **Envoy**, or cloud WAF rate limits **in front of** FluxLit. Ensure `X-Forwarded-For` and trust settings match {doc}`configuration` when deriving client IPs; see {doc}`production-tls` for tightening **`FLUXLIT_FORWARDED_ALLOW_IPS`**.

## Related

- {doc}`deployment` — edge placement and health probes.
- {doc}`production-tls` — forwarded headers and TLS at the edge.
- {doc}`observability` — gateway access logs and request IDs.
