# Observability

**Why read this:** request IDs for support tickets, optional **one-line-per-request** gateway logs for HTTP debugging, readiness (`/api/readyz`) behavior, JSON logging for aggregators, SLO-oriented alerting examples, and a recipe for OpenTelemetry later.

## Request IDs

The gateway and optional FastAPI access logging use {data}`fluxlit.logging.context.REQUEST_ID_HEADER` (`X-Request-ID`). The ID is stored in a {class}`contextvars.ContextVar` for the duration of each request; see {mod}`fluxlit.logging`.

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
- `query` — raw query string from the ASGI scope with **sensitive keys redacted** (default `fluxlit_sid`, plus {attr}`~fluxlit.config.FluxlitSettings.url_session_query_param` when set); see {mod}`fluxlit.logging.redact` and {doc}`url-session`

With the default (`False`), the same line is logged at **DEBUG** only.

If you enable gateway INFO logs in production, combine them with your normal log pipeline (filters, aggregators) and scrub or avoid echoing sensitive headers. For copying header dicts into logs or debug output, use {mod}`fluxlit.logging.redact`. Broader secrets and rotation guidance: {doc}`secrets`.

### JSON log lines (Loki / Datadog-style)

Use {class}`~fluxlit.logging.JsonLogFormatter` so each log record is a **single JSON object** with at least `time`, `level`, `logger`, `message`, plus any attributes from ``logger.info(..., extra={...})`` (for example `request_id`, `fluxlit_dispatch`, `path` from gateway access logs).

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
            "()": "fluxlit.logging.json_formatter.JsonLogFormatter",
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

## Gateway Prometheus metrics (RED)

When **`FLUXLIT_ENABLE_GATEWAY_PROMETHEUS_METRICS=1`** and **`prometheus-client`** is installed (`pip install "fluxlit[metrics]"` or include in your image), the gateway exposes **`GET`** on **`FLUXLIT_GATEWAY_PROMETHEUS_METRICS_PATH`** (default **`/__fluxlit/metrics`**) in Prometheus text format.

- **`fluxlit_gateway_requests_total`** — labels **`dispatch`** (`api` vs `streamlit`) and **`method_kind`** (HTTP method or `WEBSOCKET`).
- **`fluxlit_gateway_request_duration_seconds`** — histogram by **`dispatch`** (wall time for one gateway request; scrape path responses are excluded).

The path must **not** be under your **`api_mount_path`** or it will shadow API routes (the runtime logs a warning and disables metrics). Secure the endpoint at your ingress (allow only Prometheus scrapers) or keep metrics disabled in untrusted networks.

**USE-style saturation** (CPU, memory, file descriptors) is not emitted by FluxLit core; scrape the node or cAdvisor / kube-state-metrics alongside these application counters.

## Python `logging` filters

Use a {class}`logging.Filter` to drop noisy loggers or scrub fields before logs reach stdout or a log aggregator (in addition to {mod}`fluxlit.logging.redact` for header maps).

## OpenTelemetry (recipe)

FluxLit does not bundle OpenTelemetry. A typical approach:

1. **FastAPI:** use `opentelemetry-instrumentation-fastapi` and mount the tracer on `app.api` (the inner FastAPI app on your {class}`~fluxlit.app.FluxLit` instance).
2. **Outbound HTTP:** instrument `httpx` if you propagate traces from the API to upstreams.
3. **Streamlit subprocess:** runs in a **separate process**; treat it as its own service for tracing unless you add custom propagation via env vars.

Because the browser hits a **single port**, ingress spans should label whether work happened on the API (`/api/...`) or the Streamlit proxy path.

### Trace context (W3C `traceparent`)

The gateway already forwards **`X-Request-ID`** to Streamlit on proxied HTTP and WebSockets. For **OpenTelemetry** or other tracers, you can additionally propagate **`traceparent`** / **`tracestate`** from your edge if your proxy injects them; ensure your Streamlit and FastAPI instrumentation agree on the same trace ID format. There is **no built-in** OTel span around the gateway today — add spans in your app or use auto-instrumentation on `app.api` as in the bullets above.

## Correlation limits (gateway vs Streamlit)

- **Gateway-centered IDs:** `X-Request-ID` is set in the **gateway** ASGI process and forwarded to the Streamlit upstream. Gateway access logs and nginx can align on that header.
- **Streamlit subprocess:** Streamlit page code runs in the **child process**. The parent’s {class}`contextvars.ContextVar` used for `get_request_id()` in the gateway is **not** automatically visible inside arbitrary Streamlit callbacks. For server-side `httpx` calls from Streamlit to `/api`, use {class}`~fluxlit.client.ApiClient` with **`propagate_request_id=True`** **only when** your code has set a correlation id in that process (or pass headers explicitly). Do not assume the browser’s request id appears in Streamlit without your own propagation.

## Readiness

`GET /api/readyz` (hidden from OpenAPI) probes the Streamlit sidecar when `FLUXLIT_STREAMLIT_UPSTREAM` is set; see {mod}`fluxlit.health`. The probe requires a **2xx** response from `GET` on the upstream root (not merely “any HTTP answer”). For Kubernetes-style probe configuration and curl examples, see {doc}`deployment`. If probes fail in production, see {doc}`troubleshooting`.

## See also

- {doc}`secrets` — keep credentials out of log pipelines.
- {doc}`production-tls` — align log and probe URLs with production TLS and proxy trust.
