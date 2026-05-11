# Docker: emulated reverse-proxy deployment

Four nginx shapes are supported. Subpath scenarios use **`FLUXLIT_ROOT_PATH=/myapp`** and **`FLUXLIT_TRUST_PROXY=1`** in the FluxLit image; the root scenario overrides the root path to empty. The sample **FluxLit image** uses a **digest-pinned** Python base and runs as a **non-root** user (see `Dockerfile` in this directory). The FluxLit gateway forwards **`X-Request-ID`** to Streamlit on proxied HTTP and WebSockets so you can correlate nginx, gateway, and sidecar logs when clients send that header (or the gateway generates one).

Operator docs for TLS, HSTS, and **`forwarded_allow_ips`**: [Production TLS](https://fluxlit.readthedocs.io/en/stable/production-tls.html).


| Scenario | Compose | Public URL | Proxy behavior |
|----------|---------|------------|----------------|
| **Root path** | `+ docker-compose.root.yml` | `http://127.0.0.1:8082/` | Forwards `/api/...`, `/_stcore/...`, and `/` at origin root. |
| **Strip prefix** (default) | `docker-compose.yml` | `http://127.0.0.1:8080/myapp/` | Forwards `/api/...`, `/_stcore/...` to FluxLit (prefix stripped). |
| **Full path** | `+ docker-compose.fullpath.yml` | `http://127.0.0.1:8081/myapp/` | Forwards full URI `/myapp/...` to FluxLit (Connect-style). |
| **HTTPS** | `+ docker-compose.https.yml` | `https://127.0.0.1:8444/myapp/` | TLS at nginx; `X-Forwarded-Proto: https`. Dev certs via `generate-test-certs.sh`. |

## Run (strip-prefix)

From repository root:

```bash
docker compose -f docker/proxy-deployment/docker-compose.yml up --build
```

In another terminal (install **`pip install websockets`** once for the WebSocket check, or set **`SKIP_WS=1`**):

```bash
./docker/proxy-deployment/smoke-test.sh
```

Or open **http://127.0.0.1:8080/myapp/** in a browser.

## Full-path proxy

```bash
docker compose -f docker/proxy-deployment/docker-compose.yml -f docker/proxy-deployment/docker-compose.fullpath.yml up --build
BASE_URL=http://127.0.0.1:8081 ./docker/proxy-deployment/smoke-test.sh
```

## Root-path proxy

```bash
docker compose -f docker/proxy-deployment/docker-compose.yml -f docker/proxy-deployment/docker-compose.root.yml up --build
PUBLIC_PREFIX="" BASE_URL=http://127.0.0.1:8082 ./docker/proxy-deployment/smoke-test.sh
```

## HTTPS proxy

```bash
./docker/proxy-deployment/generate-test-certs.sh
docker compose -f docker/proxy-deployment/docker-compose.yml -f docker/proxy-deployment/docker-compose.https.yml up --build
CURL_INSECURE=1 BASE_URL=https://127.0.0.1:8444 ./docker/proxy-deployment/smoke-test.sh
```

## Run all three locally

```bash
./docker/proxy-deployment/run-all-proxy-smokes.sh
```

## What is tested

- **Backend:** `GET …/myapp/api/healthz` returns JSON `{"status":"ok"}` through nginx.
- **Readiness:** `GET …/myapp/api/readyz` reports the managed Streamlit sidecar ready.
- **Smoke API:** `GET …/myapp/api/smoke` returns the canonical `fluxlit_smoke_ok` marker.
- **Request ID:** `X-Request-ID` reaches the smoke API through the proxy.
- **Frontend:** `GET …/myapp/` returns HTML that includes Streamlit bootstrap (`_stcore` / `stApp`).
- **Body limits:** oversized proxied bodies return `413`.
- **WebSocket:** TLS-aware handshake to **`…/myapp/_stcore/stream`** with subprotocol `streamlit` (unless `SKIP_WS=1`).

**Also in CI:** Python tests under **`tests/`** cover gateway forwarding (`X-Forwarded-*`, `Host`), HTTP proxy behavior (gzip, redirects), and WebSocket paths aligned with Streamlit’s stream route — complementary to this shell smoke script.

Stop: `docker compose -f docker/proxy-deployment/docker-compose.yml down` (add extra `-f` files if you used overrides).
