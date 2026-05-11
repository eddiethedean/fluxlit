# Deployment

**You are in the right place if** you are shipping FluxLit with Docker or Kubernetes, wiring health checks, or choosing between `fluxlit dev` and **`fluxlit run`**.

FluxLit serves **one public port**: the ASGI **gateway** (Uvicorn) proxies API traffic to FastAPI and everything else to a **Streamlit subprocess**. Point browsers and load balancers at that port only; see {doc}`architecture` for the request path.

## Production entrypoint

Use **`fluxlit run`** (no reload). Typical container command:

```bash
fluxlit run app:app --host 0.0.0.0 --port 8000
```

The **`target`** (`module:attr`) resolves the same way as `fluxlit dev`: CLI argument → `fluxlit.toml` / `[tool.fluxlit]` `target` → `app:app`. Bind address and port also follow {doc}`configuration` precedence (CLI → env → project file → defaults).

Behind a reverse proxy, pass **`--proxy-headers`** (or set `FLUXLIT_TRUST_PROXY=1`) and configure `FLUXLIT_ROOT_PATH` when the app is mounted under a subpath — see the reverse-proxy section in {doc}`configuration`.

## Running under Uvicorn directly

The usual pattern matches FastAPI: your `FluxLit` instance is the ASGI app.

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

Set **`target`** in `fluxlit.toml` (or `FluxLit(import_target=...)`, or `FLUXLIT_APP`) when
the import path is not `app:app`. Set **`gateway_port`** in `fluxlit.toml` (or
`FLUXLIT_GATEWAY_PORT`) to match **`--port`** when it is not **8000**.

Legacy / factory entrypoint (same stack, requires env):

```bash
export FLUXLIT_APP="app:app"
uvicorn fluxlit.runtime:create_unified_app --factory --host 0.0.0.0 --port 8000
```

Notes:

- Uvicorn `--workers` > 1 is **not supported** for the unified stack.
- Lifespan follows the ASGI spec; the inner FastAPI app’s lifespan runs after the
  Streamlit sidecar starts.

## Health checks

| Probe | Path | Meaning |
|-------|------|--------|
| **Liveness** | `GET /api/healthz` | FastAPI app is up (does not check Streamlit). |
| **Readiness** | `GET /api/readyz` | When the unified runtime has configured a Streamlit upstream (`FLUXLIT_STREAMLIT_UPSTREAM`), returns **200** only if `GET` on the upstream root returns **2xx**. **503** on connection errors, **5xx/4xx/3xx** from the upstream, or missing upstream state. If no upstream is configured (e.g. tests), returns **200** with `streamlit: not_configured`. |

Both routes are **hidden from OpenAPI** so they do not clutter `/api/docs`. Use them in Kubernetes `livenessProbe` / `readinessProbe`, load balancers, or Compose `healthcheck` curls.

Example checks:

```bash
curl -fsS http://127.0.0.1:8000/api/healthz
curl -fsS http://127.0.0.1:8000/api/readyz
```

(kubernetes-graceful-shutdown)=
## Kubernetes: graceful shutdown

FluxLit runs **Uvicorn** and a **Streamlit child** in one pod. When Kubernetes sends **SIGTERM**, Uvicorn stops accepting new connections and drains in-flight HTTP/WebSockets up to **`timeout_graceful_shutdown`**, then runs ASGI lifespan shutdown (which tears down Streamlit). Align timeouts so the pod is not **SIGKILL** mid-drain.

- **`FLUXLIT_UVICORN_GRACEFUL_SHUTDOWN_TIMEOUT_S`** — optional; forwarded to Uvicorn as `timeout_graceful_shutdown`. Set it **below** `terminationGracePeriodSeconds`, leaving time for `preStop` hooks and for the runtime’s bounded Streamlit termination (SIGINT / terminate / kill sequence) after lifespan exits.
- **`terminationGracePeriodSeconds`** — must exceed Uvicorn’s graceful window plus any **`preStop`** sleep you add for load balancers to stop sending traffic before SIGTERM.
- **`preStop`** — common pattern: `sleep 5` (or similar) so endpoints update before the main process sees SIGTERM; alternative is active coordination with your ingress. This is **not** a substitute for Uvicorn drain; it only reduces in-flight work at cutoff.

Ordering: ingress / kube-proxy stop sending new connections → **SIGTERM** → Uvicorn drain → lifespan stops Streamlit → process exits. If drain is too long, Kubernetes still **SIGKILL** after the grace period.

## Docker and Compose

- **`fluxlit build`** writes a minimal `Dockerfile` and `.dockerignore` into the current directory (or `-o` / `--output`). Adjust the generated files for your dependency layout, base image, non-root user, and image size. The template uses `CMD ["fluxlit", "run", "<target>"]` and sets `FLUXLIT_GATEWAY_HOST=0.0.0.0`.
- A runnable **Compose** example lives in the repository at **`examples/docker_compose/`** (installs `fluxlit` from PyPI, exposes port 8000).
- For **nginx**, TLS, and subpath smoke tests, see **`docker/proxy-deployment/`** in the repo.

Do **not** run `fluxlit dev` with `--reload` in production images.

## Observability in production

- Enable **`FLUXLIT_ENABLE_GATEWAY_ACCESS_LOG=1`** only if your log pipeline can handle per-request volume; pair with filters and {mod}`fluxlit.logging_redact` where headers are copied into logs — {doc}`observability`.
- For **JSON lines** (Loki, Datadog, Cloud Logging), attach {class}`~fluxlit.logging_json.JsonLogFormatter` to your root, `uvicorn`, and `fluxlit` loggers (sample `dictConfig` in {doc}`observability`).
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
- [ ] Optional: set **`FLUXLIT_UVICORN_GRACEFUL_SHUTDOWN_TIMEOUT_S`** (and Kubernetes `terminationGracePeriodSeconds` / `preStop`) per {ref}`kubernetes-graceful-shutdown` above.
- [ ] Secrets in env or a secrets manager — not baked into images; `.env` excluded from Docker context (default `.dockerignore` from `fluxlit build` already ignores `.env`).

## Related

- {doc}`cli` — `run`, `build`, `shutdown`, PID file options.
- {doc}`testing` — proxy smoke and E2E for regression coverage.
- {doc}`troubleshooting` — common deployment and routing failures.
