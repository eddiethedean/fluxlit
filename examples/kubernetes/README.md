# Kubernetes reference (FluxLit)

Minimal **Deployment** and **Service** for running FluxLit behind a cluster load balancer. This matches the **0.5** roadmap “reference deployment” path: **non-root** image contract, **liveness** / **readiness** probes, and **graceful shutdown** alignment.

## Before you apply

1. **Build and push an image** that contains your app (not only `fluxlit` from PyPI). Start from `fluxlit build` output or `examples/docker_compose/Dockerfile` patterns: digest-pinned base, `USER appuser`, lockfile installs.
2. Edit **`deployment.yaml`**: replace `YOUR_REGISTRY/fluxlit-app:0.11.0` (or your tag) with your image; set `FLUXLIT_*` and secrets via `ConfigMap` / `Secret` (do not commit real secrets).

## Apply

```bash
kubectl apply -f examples/kubernetes/deployment.yaml
```

For an **Ingress** sketch (host, TLS, WebSocket-friendly timeouts), see `ingress.example.yaml` in this directory (not applied by default).

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
