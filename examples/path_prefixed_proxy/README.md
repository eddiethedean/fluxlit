# Path-prefixed proxy example (`/apps/my-app`)

This repository’s **canonical** runnable reverse-proxy examples live under **`../docker/proxy-deployment/`** (strip-prefix, full-path, root, HTTPS, and **`/apps/my-app`**).

Use the **`/apps/my-app`** stack when your public URL looks like:

`https://<host>/apps/my-app/`

## Quick start

From the repository root:

```bash
docker compose -f docker/proxy-deployment/docker-compose.yml \
  -f docker/proxy-deployment/docker-compose.apps-prefix.yml up --build
```

In another terminal:

```bash
PUBLIC_PREFIX=/apps/my-app BASE_URL=http://127.0.0.1:8083 \
  ./docker/proxy-deployment/smoke-test.sh
```

FluxLit in that Compose override sets **`FLUXLIT_ROOT_PATH=/apps/my-app`** and **`FLUXLIT_PUBLIC_BASE_URL=http://127.0.0.1:8083/apps/my-app`** to match nginx.

## Documentation

- [Production TLS and edge headers](https://fluxlit.readthedocs.io/en/stable/production-tls.html) — TLS termination, **`X-Forwarded-*`**, **`FLUXLIT_FORWARDED_ALLOW_IPS`**, URL table, troubleshooting with **`fluxlit doctor`**.
