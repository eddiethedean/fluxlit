# Deployment

FluxLit serves **one public port**: the ASGI **gateway** (Uvicorn) proxies API traffic to FastAPI and everything else to a **Streamlit subprocess**. Production deployments should treat that port as the only ingress from browsers; see {doc}`architecture` for the request path.

## Production entrypoint

Use **`fluxlit run`** (no reload). Typical container command:

```bash
fluxlit run app:app --host 0.0.0.0 --port 8000
```

The **`target`** (`module:attr`) resolves the same way as `fluxlit dev`: CLI argument → `fluxlit.toml` / `[tool.fluxlit]` `target` → `app:app`. Bind address and port also follow {doc}`configuration` precedence (CLI → env → project file → defaults).

Behind a reverse proxy, pass **`--proxy-headers`** (or set `FLUXLIT_TRUST_PROXY=1`) and configure `FLUXLIT_ROOT_PATH` when the app is mounted under a subpath — see the reverse-proxy section in {doc}`configuration`.

## Health checks

| Probe | Path | Meaning |
|-------|------|--------|
| **Liveness** | `GET /api/healthz` | FastAPI app is up (does not check Streamlit). |
| **Readiness** | `GET /api/readyz` | When the unified runtime has configured a Streamlit upstream (`FLUXLIT_STREAMLIT_UPSTREAM`), returns **200** if the sidecar responds with an HTTP status below 500, **503** if not. If no upstream is configured (e.g. tests), returns **200** with `streamlit: not_configured`. |

Both routes are **hidden from OpenAPI** so they do not clutter `/api/docs`. Use them in Kubernetes `livenessProbe` / `readinessProbe`, load balancers, or Compose `healthcheck` curls.

Example checks:

```bash
curl -fsS http://127.0.0.1:8000/api/healthz
curl -fsS http://127.0.0.1:8000/api/readyz
```

## Docker and Compose

- **`fluxlit build`** writes a minimal `Dockerfile` and `.dockerignore` into the current directory (or `-o` / `--output`). Adjust the generated files for your dependency layout, base image, non-root user, and image size. The template uses `CMD ["fluxlit", "run", "<target>"]` and sets `FLUXLIT_GATEWAY_HOST=0.0.0.0`.
- A runnable **Compose** example lives in the repository at **`examples/docker_compose/`** (installs `fluxlit` from PyPI, exposes port 8000).
- For **nginx**, TLS, and subpath smoke tests, see **`docker/proxy-deployment/`** in the repo.

Do **not** run `fluxlit dev` with `--reload` in production images.

## Observability in production

- Enable **`FLUXLIT_ENABLE_GATEWAY_ACCESS_LOG=1`** only if your log pipeline can handle per-request volume; pair with filters and {mod}`fluxlit.logging_redact` where headers are copied into logs — {doc}`observability`.
- **`FLUXLIT_ENABLE_REQUEST_LOGGING`** affects the **inner FastAPI** app only (not the gateway dispatch line).

## Runtime-injected environment

The parent process sets variables for the Streamlit child and for gateway code that reads upstream state. You normally **do not** set these by hand when using `fluxlit run`; see {ref}`runtime-env`.

## Scaling and workers

- **Single Uvicorn process** is the typical model: one gateway and **one** Streamlit child share localhost and env state.
- Multiple replicas behind a load balancer each run their own Streamlit process; use **sticky sessions** or accept that Streamlit sessions are per-replica unless you add external session affinity.
- Uvicorn **multiple workers** (`--workers` greater than 1) with the unified stack is **not** a supported configuration for one container: extra workers would not share the same Streamlit subprocess contract. Scale **horizontally** with more pods/instances instead.

## Checklist

- [ ] `fluxlit doctor` passes (or only acceptable WARNs).
- [ ] `FLUXLIT_GATEWAY_HOST` / bind address matches container/platform (often `0.0.0.0`).
- [ ] Proxy: `FLUXLIT_TRUST_PROXY`, `FLUXLIT_ROOT_PATH`, and `FLUXLIT_PUBLIC_BASE_URL` (for OAuth) set correctly.
- [ ] Readiness probe uses `/api/readyz` when Streamlit must be up before receiving traffic.
- [ ] Secrets in env or a secrets manager — not baked into images; `.env` excluded from Docker context (default `.dockerignore` from `fluxlit build` already ignores `.env`).

## Related

- {doc}`cli` — `run`, `build`, `shutdown`, PID file options.
- {doc}`testing` — proxy smoke and E2E for regression coverage.
- {doc}`troubleshooting` — common deployment and routing failures.
