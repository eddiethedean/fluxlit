# Runbooks

Short **symptom → check → mitigate** notes for common production incidents. Pair with {doc}`troubleshooting` for local/dev issues and {doc}`deployment` for probes and Kubernetes.

## 503 on `GET /api/readyz`

**Symptom:** Load balancer or user sees **503** from `/api/readyz`; Kubernetes may mark the pod **NotReady**.

**Meaning:** When `FLUXLIT_STREAMLIT_UPSTREAM` is set, readiness requires **HTTP 2xx** from `GET` on the Streamlit upstream root. Anything else (connection refused, timeout, 4xx/5xx/3xx) returns **503**.

**Checks**

1. `curl -v http://<pod-ip>:8000/api/readyz` — read JSON `detail`.
2. `curl -v http://<upstream-from-env>/` — same URL the probe uses (root path on Streamlit).
3. Gateway / Streamlit logs: slow start, crash loop, wrong upstream URL after reload.
4. `fluxlit doctor <target>` on a shell with the same env (if you can exec into the container).

**Mitigations**

- Increase **startup** time: readiness `initialDelaySeconds`, or fix Streamlit startup cost.
- Fix **wrong upstream** (stale `FLUXLIT_STREAMLIT_UPSTREAM` / state file after restart).
- If Streamlit is intentionally down for maintenance, accept **NotReady** traffic drain or use a separate maintenance mode.

## Blank Streamlit UI (white page, spinner forever)

**Symptom:** `/api/healthz` is **200** but `/` or `/_stcore/...` shows blank or endless loading.

**Checks**

1. Browser devtools **Network**: failed `/_stcore/stream` WebSocket or 4xx/5xx on static assets.
2. **`FLUXLIT_ROOT_PATH`**: must match browser-visible prefix; missing or wrong path breaks asset URLs ({doc}`configuration`).
3. **`FLUXLIT_TRUST_PROXY`**: if behind TLS or subpath termination, scheme/host headers must match public URL.
4. Gateway logs with **`FLUXLIT_ENABLE_GATEWAY_ACCESS_LOG=1`** and `request_id` correlation ({doc}`observability`).

**Mitigations**

- Align `root_path`, proxy `X-Forwarded-*`, and nginx location blocks — see `docker/proxy-deployment/` smoke tests and {doc}`production-tls`.
- Verify WebSocket upgrade through the edge proxy (timeouts, buffering).

## WebSocket failures behind nginx / Traefik

**Symptom:** Streamlit disconnects, “Connection error”, or WS closes immediately.

**Checks**

1. Proxy **`Upgrade`** and **`Connection`** headers passed through to the FluxLit port.
2. Idle / read timeouts on the proxy **greater than** Streamlit/WebSocket heartbeats; align with **`FLUXLIT_GATEWAY_WS_*`** settings ({doc}`configuration`).
3. Subpath: WebSocket URL must include the same prefix as HTTP (`/myapp/_stcore/stream`).

**Mitigations**

- Use the repo’s **proxy-deployment** nginx configs as a reference; increase proxy `proxy_read_timeout` (nginx) or equivalent.
- For TLS termination at the edge, confirm `wss://` and certificates match what the browser uses.

## Auth misconfig (401 / 403, login loops, `fluxlit doctor` FAIL)

**Symptom:** API returns **401/403**; OIDC redirect errors; doctor reports JWT/auth FAIL.

**Checks**

1. `pip install "fluxlit[auth]"` in the image if using JWT/OIDC helpers.
2. Env: `FLUXLIT_JWT_*`, `FLUXLIT_PUBLIC_BASE_URL`, `FLUXLIT_OIDC_*`, clock skew (NTP).
3. **`FLUXLIT_INTERNAL_API_BASE`** still loopback-safe and consistent with `api_mount_path`.
4. BFF / OIDC: remember **in-memory** `state` store requires **single replica** or externalized store ({doc}`security`).

**Mitigations**

- Fix issuer/audience/JWKS URL; rotate secrets per {doc}`secrets`.
- For subpath deployments, set **`FLUXLIT_ROOT_PATH`** and **`FLUXLIT_PUBLIC_BASE_URL`** to the public origin.

## Multi-replica: new Streamlit session after refresh

**Symptom:** Users report losing UI state or “starting over” after **F5** or intermittent **503** / reconnects, only when **more than one** FluxLit replica is behind the load balancer.

**Meaning:** Each replica has its own Streamlit process and **in-memory** `st.session_state`. Without **sticky routing** or a **shared store** (URL session + external `SessionStore`, or app-level persistence), the next request may hit a different replica.

**Checks**

1. Confirm replica count > 1 and whether the LB uses **affinity** (cookie / IP / connection).
2. If using FluxLit **URL-session** helpers, verify the store is **shared** across replicas (not `InMemorySessionStore` per pod).
3. For **OIDC BFF**, confirm you are not relying on single-replica in-memory `state` without affinity — see {doc}`security`.

**Mitigations**

- Add **session affinity** on the Service or ingress (see `examples/kubernetes/service-session-affinity.example.yaml` in the repo), **or**
- Move continuity data to an **external `SessionStore`** or database — see {doc}`url-session` and {doc}`deployment` (scaling checklist).

## Scripted load and chaos (repository)

Repeatable scripts live under **`scripts/`** in the repository:

| Script | Role |
|--------|------|
| **`soak_http.sh`** | Many GETs with **`curl -f`** (2xx only) — default `PATH_SUFFIX=/api/healthz`. |
| **`soak_readyz.sh`** | Many GETs on **`/api/readyz`** without `-f`; counts **2xx vs 503** and latency percentiles (`REQUIRE_2XX=0` to investigate flaky readyz). |
| **`chaos_graceful_shutdown.sh`** | SIGTERM → gateway exits within a bounded window. |
| **`chaos_streamlit_kill.sh`** | Kill Streamlit child → parent exits. |
| **`chaos_slow_upstream.sh`**, **`chaos_oversized_body.sh`**, **`chaos_dropped_websocket.sh`** | Timeout, **413**, and WebSocket drop behaviors. |
| **`soak_metrics.sh`** | Many GETs on **`/__fluxlit/metrics`** (or `FLUXLIT_GATEWAY_PROMETHEUS_METRICS_PATH`); expects **200** and Prometheus text with **`fluxlit_gateway_requests_total`**. Requires **`FLUXLIT_ENABLE_GATEWAY_PROMETHEUS_METRICS=1`** and `prometheus-client`. |

Run **`./scripts/run_smoke_app.sh`** (or your app) in one terminal, then point **`BASE_URL`** at it. For CI-style signals, pair with {doc}`observability` (metrics, gateway logs) and {doc}`deployment` (readiness).

### Soak methodology and baselines

Soak scripts are **relative** measurements: they report request counts, HTTP status mix (for `soak_readyz.sh`), and **p50/p95/p99** latency in milliseconds over **`COUNT`** iterations. They do **not** assert absolute SLOs — operators should compare runs on the **same machine class** (for example the same Kubernetes node pool or CI `runs-on` label) and record **commit SHA + date** when publishing reference numbers.

**What to record:** `COUNT`, `BASE_URL`, `PATH_SUFFIX`, relevant `FLUXLIT_*` flags (metrics, proxy trust), CPU/memory snapshot if available, and the script’s final summary line or `OUTPUT_FORMAT=json` payload.

**Under load, FluxLit emits:** gateway access log extras (when enabled) with stable keys listed in {doc}`support-matrix`; gateway **RED** metrics (when `FLUXLIT_ENABLE_GATEWAY_PROMETHEUS_METRICS=1`); **DEBUG** lines on `fluxlit.gateway` for histogram observe failures (request still completes). **Not emitted:** USE-style host saturation metrics from FluxLit core — scrape the node or cAdvisor ({doc}`observability`).

**Correlation limits:** `request_id` ties gateway access logs to the internal hop; Streamlit runs in a **separate process**, so its logs use the same id only where the runtime forwards it — see {doc}`observability` correlation section.

## Related

- {doc}`troubleshooting` — doctor, ports, API path mistakes.
- {doc}`observability` — logs, JSON formatters, SLO-style alerts.
- {doc}`secrets` — credentials and rotation.
