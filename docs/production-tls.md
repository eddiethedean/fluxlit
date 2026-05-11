# Production TLS and edge headers

**Read this before** exposing FluxLit on the public internet: where TLS terminates, how **HSTS** and **forwarded headers** interact with Uvicorn, and why **Content-Security-Policy** is usually an edge concern—not a one-line toggle for Streamlit.

For deployment basics (health probes, Docker, graceful shutdown), see {doc}`deployment`. For env reference, see {doc}`configuration`. For correlation and gateway logs, see {doc}`observability`.

## Terminate TLS where you test

- Use the **same termination model** in staging as production (same ingress, same `X-Forwarded-*` behavior, same certificate chain validation).
- The repository’s **`docker/proxy-deployment/`** includes **HTTPS** Compose (`docker-compose.https.yml`) and `generate-test-certs.sh` plus `smoke-test.sh`—use it to validate subpath routing and headers against **real TLS**, not only plain HTTP to localhost.

## HSTS: edge vs application

FluxLit’s optional {class}`~fluxlit.security_middleware.SecurityHeadersMiddleware` (enable with **`FLUXLIT_ENABLE_SECURITY_HEADERS`**) sets **Strict-Transport-Security** when the request’s effective scheme is **HTTPS** (from `X-Forwarded-Proto` first value or the URL scheme). That only applies to responses served by this stack.

- If your **CDN or ingress** already sends **HSTS**, avoid **duplicating** conflicting directives (different `max-age` or `includeSubDomains`). Prefer **one owner**—usually the outermost TLS terminator.
- If TLS terminates **only** at the edge, the app must see **`X-Forwarded-Proto: https`** (see trust settings below) or it will not emit HSTS from the middleware path.

## Trusting proxies: `forwarded_allow_ips`

When **`FLUXLIT_TRUST_PROXY`** is on (or `fluxlit run --proxy-headers`), Uvicorn trusts **`X-Forwarded-*`** for client IP and scheme. **`FLUXLIT_FORWARDED_ALLOW_IPS`** is forwarded to Uvicorn as **`forwarded_allow_ips`**.

- **Default when trusting proxy and unset:** `*` (trust all connecting IPs). That is convenient in dev and risky if clients can reach the app **without** going through your proxy.
- **Production:** set **`FLUXLIT_FORWARDED_ALLOW_IPS`** to your **load balancer / ingress CIDRs** or link-local ranges your mesh uses—see [Uvicorn settings](https://www.uvicorn.org/settings/#http) for the exact string format (comma-separated IPs or networks).

### nginx: real client IP and forwarded scheme

Your proxy must set **`X-Forwarded-Proto`** (and typically **`X-Forwarded-For`**) from **trusted** variables (e.g. `$scheme` from the TLS listener), not from user-controlled input.

Example patterns (conceptual—adapt to your `docker/proxy-deployment` layout):

```nginx
# Trust only your edge/load balancer when using real_ip (example)
set_real_ip_from 10.0.0.0/8;
real_ip_header X-Forwarded-For;

proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
```

The repo’s **`docker/proxy-deployment/nginx.conf`** is the maintained reference for strip-prefix and subpath smoke tests.

## Content-Security-Policy (CSP) and Streamlit

Streamlit serves **dynamic scripts**, **WebSockets**, and assets that evolve with versions. A **strict CSP** copied from a generic SPA guide will often **break** the UI (inline script hashes drift, `connect-src` for websockets, `frame-ancestors` for embedding).

Practical guidance:

- Treat **CSP as optional** for the Streamlit-heavy routes unless you have tested every page with your Streamlit version.
- Prefer **tight CSP on separate static sites** (marketing, docs) and **minimal, deliberate** directives on **`/api`** if you add middleware yourself.
- FluxLit’s built-in middleware does **not** set **CSP** today; adding a global CSP belongs in your **ingress** or a carefully scoped FastAPI middleware after testing.

## Validate TLS end-to-end (quick runbook)

1. Build and start the HTTPS stack under **`docker/proxy-deployment/`** (see that directory’s README).
2. From the host, call through the **TLS** listener (see `BASE_URL` in smoke scripts), e.g.:

   ```bash
   CURL_INSECURE=1 curl -fsSI https://127.0.0.1:8444/myapp/api/healthz
   ```

   Use your real CA in production instead of `CURL_INSECURE`.
3. Confirm **`Strict-Transport-Security`** appears when the app believes the request is HTTPS (directly or via `X-Forwarded-Proto`).
4. Confirm **`GET /api/readyz`** returns **200** when Streamlit is configured and healthy.

## Read-only root filesystem (Kubernetes)

Enabling **`securityContext.readOnlyRootFilesystem: true`** is compatible in principle but requires **writable mounts** for anything the process must write at runtime (for example **`TMPDIR`**, Streamlit cache directories under the user home, pidfile paths if used, and uploaded temp files). Start with a **tmpfs** mount for `/tmp` and an **`emptyDir`** for a dedicated cache path; validate with your exact image and `fluxlit run` flags before rolling out cluster-wide.

## Related

- {doc}`configuration` — `FLUXLIT_TRUST_PROXY`, `FLUXLIT_FORWARDED_ALLOW_IPS`, `FLUXLIT_ENABLE_SECURITY_HEADERS`, `FLUXLIT_PUBLIC_BASE_URL`.
- {doc}`secrets` — no secrets in access logs; header redaction.
- {doc}`deployment` — Docker, Compose, Kubernetes graceful shutdown.
