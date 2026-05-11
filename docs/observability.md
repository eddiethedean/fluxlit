# Observability

**Why read this:** request IDs for support tickets, optional **one-line-per-request** gateway logs for HTTP debugging, readiness (`/api/readyz`) behavior, JSON logging for aggregators, SLO-oriented alerting examples, and a recipe for OpenTelemetry later.

## Request IDs

The gateway and optional FastAPI access logging use {data}`fluxlit.logging_context.REQUEST_ID_HEADER` (`X-Request-ID`). The ID is stored in a {class}`contextvars.ContextVar` for the duration of each request; see {mod}`fluxlit.logging_context`.

The gateway **replaces** `X-Request-ID` on the **Streamlit upstream** (HTTP and WebSocket) with that same resolved value so sidecar access logs can join to gateway and API lines.

### Correlation path

```text
flowchart LR
  browser[Browser]
  gw[FluxLit gateway]
  api[FastAPI /api]
  st[Streamlit sidecar]

  browser -->|"X-Request-ID (optional)"| gw
  gw -->|"X-Request-ID (authoritative)"| st
  gw --> api
```

For **Streamlit → `/api`** calls from Python, correlation is separate processes unless you pass a header explicitly (advanced: propagate from browser context when your Streamlit version exposes it).

## Structured gateway logs

When {attr}`~fluxlit.config.FluxlitSettings.enable_gateway_access_log` is `True`, the gateway emits **one INFO log per request** with `extra` fields:

- `fluxlit_dispatch` — `api` or `streamlit`
- `http_method_or_type` — HTTP method or `websocket`
- `path` — ASGI path seen by the gateway

With the default (`False`), the same line is logged at **DEBUG** only.

If you enable gateway INFO logs in production, combine them with your normal log pipeline (filters, aggregators) and scrub or avoid echoing sensitive headers. For copying header dicts into logs or debug output, use {mod}`fluxlit.logging_redact`. Broader secrets and rotation guidance: {doc}`secrets`.

### JSON log lines (Loki / Datadog-style)

Use {class}`~fluxlit.logging_json.JsonLogFormatter` so each log record is a **single JSON object** with at least `time`, `level`, `logger`, `message`, plus any attributes from ``logger.info(..., extra={...})`` (for example `request_id`, `fluxlit_dispatch`, `path` from gateway access logs).

Suggested field conventions for log stacks:

| Field | Role |
|-------|------|
| `time` | Event timestamp (formatter output). |
| `level` / `logger` | Filter and split by component. |
| `message` | Human-readable line. |
| `request_id` | Join gateway, API, and upstream Streamlit lines when present. |
| `fluxlit_dispatch` | `api` vs `streamlit` for quick routing dashboards. |

Attach the formatter to **Uvicorn** and your app loggers via `logging.dictConfig` (often from a small Python file referenced by `LOGGING_CONFIG` or equivalent in your process manager):

```python
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "fluxlit.logging_json.JsonLogFormatter",
        },
    },
    "handlers": {
        "default": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "loggers": {
        "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
        "uvicorn.error": {"handlers": ["default"], "level": "INFO", "propagate": False},
        "uvicorn.access": {"handlers": ["default"], "level": "INFO", "propagate": False},
        "fluxlit": {"handlers": ["default"], "level": "INFO", "propagate": False},
        "fluxlit.gateway": {"handlers": ["default"], "level": "INFO", "propagate": False},
    },
    "root": {"handlers": ["default"], "level": "WARNING"},
}
```

Then `logging.config.dictConfig(LOGGING)` during startup, or point Uvicorn at a module path that does the same. Tune levels per environment; avoid duplicating access logs if both Uvicorn access and `fluxlit.gateway` INFO lines are too chatty.

## SLOs & alerting

FluxLit does not ship Prometheus rules or managed alerts; operators should define **SLOs** on the same probes documented in {doc}`deployment`.

**Liveness (`GET /api/healthz`)** — the inner API process responds; use for **restart if wedged** style checks. Example SLO: *99.9% of probes succeed* over 30 days; alert on sustained probe failure (Pod restarts) rather than single blips.

**Readiness (`GET /api/readyz`)** — when Streamlit upstream is configured, **503** means the sidecar is not accepting traffic the way the gateway expects. Example SLO: *readyz success rate* (or **error budget** when expressed as allowed 503 minutes per month). Burn alerts when the **5xx rate on readyz** rises over a short window (e.g. 5m) while healthz stays green — that pattern isolates Streamlit/upstream issues.

Example **Kubernetes** probes (paths depend on `api_mount_path`, default `/api`):

```yaml
livenessProbe:
  httpGet:
    path: /api/healthz
    port: http
  periodSeconds: 10
readinessProbe:
  httpGet:
    path: /api/readyz
    port: http
  periodSeconds: 5
```

Example **Prometheus** alert sketch (adjust labels and `job` to your setup): fire when `rate(http_requests_total{path="/api/readyz",status="503"}[5m])` is above a small threshold while healthz success stays high — indicating Streamlit or upstream misconfiguration rather than total process death.

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

## See also

- {doc}`secrets` — keep credentials out of log pipelines.
- {doc}`production-tls` — align log and probe URLs with production TLS and proxy trust.
