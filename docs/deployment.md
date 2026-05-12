# Deployment

**You are in the right place if** you are shipping FluxLit with Docker or Kubernetes, wiring health checks, or choosing between `fluxlit dev` and **`fluxlit run`**.

FluxLit serves **one public port**: the ASGI **gateway** (Uvicorn) proxies API traffic to FastAPI and everything else to a **Streamlit subprocess**. Point browsers and load balancers at that port only; see {doc}`architecture` for the request path.

## Production entrypoint

Use **`fluxlit run`** (no reload). Typical container command:

```bash
fluxlit run app:app --host 0.0.0.0 --port 8000
```

The **`target`** (`module:attr`) resolves the same way as `fluxlit dev`: CLI argument → `fluxlit.toml` / `[tool.fluxlit]` `target` → `app:app`. Bind address and port also follow {doc}`configuration` precedence (CLI → env → project file → defaults).

Behind a reverse proxy, pass **`--proxy-headers`** (or set `FLUXLIT_TRUST_PROXY=1`) and configure `FLUXLIT_ROOT_PATH` when the app is mounted under a subpath — see the reverse-proxy section in {doc}`configuration`. For a **multi-segment** public path such as **`/apps/my-app`**, nginx Compose, smoke checks, and TLS/trust notes, see {ref}`path-prefix-apps` in {doc}`production-tls` and **`docker/proxy-deployment/docker-compose.apps-prefix.yml`** in the repository.

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

- **`fluxlit build`** writes a minimal `Dockerfile` and `.dockerignore` into the current directory (or `-o` / `--output`). Adjust the generated files for your dependency layout, base image digest, non-root user, and image size. The template uses a **digest-pinned** `python:3.12-slim` base, runs as **`appuser`**, `CMD ["fluxlit", "run", "<target>"]`, and sets `FLUXLIT_GATEWAY_HOST=0.0.0.0`. Refresh the `FROM python@sha256:…` line when you intentionally upgrade the base image (match `docker pull python:3.12-slim` then inspect **RepoDigests**).
- **Production images** should install from a **committed lockfile** (`pip-tools` / `uv`, etc.) your app controls; `fluxlit build` stays minimal on purpose.
- A runnable **Compose** example lives in the repository at **`examples/docker_compose/`** (`requirements.txt` from **`pip-compile`**, exposes port 8000).
- For **nginx**, TLS, and subpath smoke tests, see **`docker/proxy-deployment/`** in the repo.

Do **not** run `fluxlit dev` with `--reload` in production images.

For **TLS termination**, **HSTS**, **forwarded header trust**, and **CSP** guidance, see {doc}`production-tls`. For **secrets**, **logs**, and **JWT/OIDC rotation**, see {doc}`secrets`.

## Observability in production

- Enable **`FLUXLIT_ENABLE_GATEWAY_ACCESS_LOG=1`** only if your log pipeline can handle per-request volume; pair with filters and {mod}`fluxlit.logging.redact` where headers are copied into logs — {doc}`observability`.
- For **JSON lines** (Loki, Datadog, Cloud Logging), attach {class}`~fluxlit.logging.JsonLogFormatter` to your root, `uvicorn`, and `fluxlit` loggers (sample `dictConfig` in {doc}`observability`).
- **`FLUXLIT_ENABLE_REQUEST_LOGGING`** affects the **inner FastAPI** app only (not the gateway dispatch line).

## Runtime-injected environment

The parent process sets variables for the Streamlit child and for gateway code that reads upstream state. You normally **do not** set these by hand when using `fluxlit run`; see {ref}`runtime-env`.

## Scaling and workers

### Single process (default)

- **One Uvicorn worker** is the supported model: one gateway ASGI app and **one** Streamlit child share loopback and process-local state (upstream URL file, OIDC BFF in-memory stores, etc.).
- **Uvicorn `--workers` > 1** is **not supported** for this unified stack in one OS process: extra workers would each try to own a Streamlit subprocess and shared resources would diverge. Do not enable multi-worker on one pod to “use all CPUs”; scale **out** instead (see below).

### Horizontal scale (multiple replicas)

Behind a **Layer 7 load balancer** or Kubernetes **Service** with multiple endpoints:

- Each replica runs **its own** gateway + Streamlit pair. **Streamlit’s default session** is tied to the server-side script run and WebSocket; after a hard refresh or new connection, users may land on a **different replica** and see a **new session** unless you add **affinity**.
- **Sticky sessions** (session affinity / cookie-based or IP-hash) route the same browser to the same replica for a period. That improves continuity for interactive UIs but is **not** a full multi-replica session store: long-lived affinity tables, draining nodes, and failures still drop local state.
- **When to add an external session store:** if you need **consistent application state across replicas** without sticky sessions (or in addition to them), persist state outside the process (database, Redis, etc.). FluxLit’s URL-session helpers provide the cookie-free binding pattern; production multi-replica continuity still depends on the store you choose.

### Rollout and drain playbook

For multi-replica deployments:

1. Run one FluxLit process per replica. Do not use Uvicorn worker fan-out inside a replica.
2. Use readiness (`/api/readyz`) to remove a replica before it receives user traffic.
3. Give Streamlit WebSockets time to close during rollouts by aligning `preStop`,
   `terminationGracePeriodSeconds`, and
   `FLUXLIT_UVICORN_GRACEFUL_SHUTDOWN_TIMEOUT_S`.
4. If users must survive replica replacement or non-sticky routing, store continuity
   state in an external `SessionStore`; in-memory stores are per replica.
5. Keep sticky sessions as a routing optimization, not as the only persistence layer
   for important app state.

### Supported alternatives to multi-worker

- **One process per replica** (Kubernetes Pod, ECS task, VM): scale replica count; tune CPU for a single process.
- **Split topology** (advanced): run Streamlit and the API on different hosts and point `FLUXLIT_STREAMLIT_UPSTREAM` at the Streamlit origin—only if your platform requires separate services and you accept operational complexity.
- **Multiple Uvicorn workers for API-only** does not apply to `FluxLit` unified mode; use plain FastAPI + separate Streamlit hosting if you truly need multi-worker HTTP for the API only.

### Reference: Kubernetes

A minimal **Deployment + Service** that matches the hardened image contract (probes, graceful shutdown, non-root) lives in **`examples/kubernetes/`** in the repository. Copy and adjust image name, resources, and `ConfigMap` / `Secret` wiring for your cluster.

## Checklist

- [ ] `fluxlit doctor` passes (or only acceptable WARNs).
- [ ] Optional CI gate: `fluxlit doctor app:app --json` is parsed and checked for unexpected `FAIL` diagnostics.
- [ ] `FLUXLIT_GATEWAY_HOST` / bind address matches container/platform (often `0.0.0.0`).
- [ ] Proxy: `FLUXLIT_TRUST_PROXY`, `FLUXLIT_ROOT_PATH`, and `FLUXLIT_PUBLIC_BASE_URL` (for OAuth) set correctly.
- [ ] Readiness probe uses `/api/readyz` when Streamlit must be up before receiving traffic.
- [ ] Optional: set **`FLUXLIT_UVICORN_GRACEFUL_SHUTDOWN_TIMEOUT_S`** (and Kubernetes `terminationGracePeriodSeconds` / `preStop`) per {ref}`kubernetes-graceful-shutdown` above.
- [ ] Secrets in env or a secrets manager — not baked into images; `.env` excluded from Docker context (default `.dockerignore` from `fluxlit build` already ignores `.env`). See {doc}`secrets`.
- [ ] **`FLUXLIT_FORWARDED_ALLOW_IPS`** tightened when **`FLUXLIT_TRUST_PROXY`** is on (not `*` in untrusted networks). See {doc}`production-tls`.
- [ ] For Kubernetes: start from **`examples/kubernetes/`** and align probes and `terminationGracePeriodSeconds` with {ref}`kubernetes-graceful-shutdown`.

## Related

- {doc}`cli` — `run`, `build`, `shutdown`, PID file options.
- {doc}`platforms` — deployment notes for common container platforms and Posit hosts.
- {doc}`production-tls` — HSTS, CSP notes, `forwarded_allow_ips`, TLS validation.
- {doc}`secrets` — secret stores, logs, JWT/OIDC rotation.
- {doc}`testing` — proxy smoke and E2E for regression coverage.
- {doc}`troubleshooting` — common deployment and routing failures.
- {doc}`runbooks` — `readyz` 503, blank Streamlit, WebSocket and auth incidents.
