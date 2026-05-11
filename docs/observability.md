# Observability

**Why read this:** request IDs for support tickets, optional **one-line-per-request** gateway logs for HTTP debugging, readiness (`/api/readyz`) behavior, and a recipe for OpenTelemetry later.

## Request IDs

The gateway and optional FastAPI access logging use {data}`fluxlit.logging_context.REQUEST_ID_HEADER` (`X-Request-ID`). The ID is stored in a {class}`contextvars.ContextVar` for the duration of each request; see {mod}`fluxlit.logging_context`.

## Structured gateway logs

When {attr}`~fluxlit.config.FluxlitSettings.enable_gateway_access_log` is `True`, the gateway emits **one INFO log per request** with `extra` fields:

- `fluxlit_dispatch` — `api` or `streamlit`
- `http_method_or_type` — HTTP method or `websocket`
- `path` — ASGI path seen by the gateway

With the default (`False`), the same line is logged at **DEBUG** only.

If you enable gateway INFO logs in production, combine them with your normal log pipeline (filters, aggregators) and scrub or avoid echoing sensitive headers. For copying header dicts into logs or debug output, use {mod}`fluxlit.logging_redact`.

## Python `logging` filters

Use a {class}`logging.Filter` to drop noisy loggers or scrub fields before logs reach stdout or a log aggregator (in addition to {mod}`fluxlit.logging_redact` for header maps).

## OpenTelemetry (recipe)

FluxLit does not bundle OpenTelemetry. A typical approach:

1. **FastAPI:** use `opentelemetry-instrumentation-fastapi` and mount the tracer on `app.api` (the inner FastAPI app on your {class}`~fluxlit.app.FluxLit` instance).
2. **Outbound HTTP:** instrument `httpx` if you propagate traces from the API to upstreams.
3. **Streamlit subprocess:** runs in a **separate process**; treat it as its own service for tracing unless you add custom propagation via env vars.

Because the browser hits a **single port**, ingress spans should label whether work happened on the API (`/api/...`) or the Streamlit proxy path.

## Readiness

`GET /api/readyz` (hidden from OpenAPI) probes the Streamlit sidecar when `FLUXLIT_STREAMLIT_UPSTREAM` is set; see {mod}`fluxlit.health`. The probe requires a **2xx** response from `GET` on the upstream root (not merely “any HTTP answer”). For Kubernetes-style probe configuration and curl examples, see {doc}`deployment`. If probes fail in production, see {doc}`troubleshooting`.
