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

## Related

- {doc}`troubleshooting` — doctor, ports, API path mistakes.
- {doc}`observability` — logs, JSON formatters, SLO-style alerts.
- {doc}`secrets` — credentials and rotation.
