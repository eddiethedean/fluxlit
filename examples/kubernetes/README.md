# Kubernetes reference (FluxLit)

Minimal **Deployment** and **Service** for running FluxLit behind a cluster load balancer. This matches the **0.5** roadmap “reference deployment” path: **non-root** image contract, **liveness** / **readiness** probes, and **graceful shutdown** alignment.

## Before you apply

1. **Build and push an image** that contains your app (not only `fluxlit` from PyPI). Start from `fluxlit build` output or `examples/docker_compose/Dockerfile` patterns: digest-pinned base, `USER appuser`, lockfile installs.
2. Edit **`deployment.yaml`**: replace `YOUR_REGISTRY/fluxlit-app:0.12.0` (or your tag) with your image; set `FLUXLIT_*` and secrets via `ConfigMap` / `Secret` (do not commit real secrets).

## Optional manifests (examples only)

These files are **not** applied by `kubectl apply -f deployment.yaml` alone. Copy or merge when you need multi-replica hardening:

| File | Purpose |
|------|---------|
| **`service-session-affinity.example.yaml`** | `sessionAffinity: ClientIP` on the Service — see [Deployment](https://fluxlit.readthedocs.io/en/stable/deployment.html) and [Runbooks](https://fluxlit.readthedocs.io/en/stable/runbooks.html) before enabling. |
| **`pod-disruption-budget.example.yaml`** | PDB with `minAvailable: 1` during node drains / upgrades. |

For **Ingress** (host, TLS, WebSocket-friendly timeouts), see `ingress.example.yaml` in this directory (not applied by default).

## Apply

```bash
kubectl apply -f examples/kubernetes/deployment.yaml
```

Port-forward for a quick smoke test:

```bash
kubectl port-forward deploy/fluxlit-app 8000:8000
curl -fsS http://127.0.0.1:8000/api/healthz
curl -fsS http://127.0.0.1:8000/api/readyz
```

## Read-only root (optional)

The Deployment comments show optional **`readOnlyRootFilesystem: true`** with **`emptyDir`** mounts for `/tmp` and a writable home/cache path. Validate with your Streamlit version (caches, uploads) before enforcing in production. See {doc}`production-tls` and {doc}`deployment`.

## Docs

- [Deployment](https://fluxlit.readthedocs.io/en/stable/deployment.html) — probes, graceful shutdown, scaling.
- [Runbooks](https://fluxlit.readthedocs.io/en/stable/runbooks.html) — common incidents (`readyz` 503, blank UI, WebSockets, auth).
