# Secrets lifecycle

How to keep **credentials and tokens** out of logs, images, and the wrong process—and how to rotate **JWT** and **OIDC** signing material without taking unrelated dependencies offline.

For architecture and token placement, see {doc}`security` and {doc}`auth-recipes`. For gateway and JSON logging, see {doc}`observability`. For TLS and HSTS at the edge, see {doc}`production-tls`.

## Principles

- **Never bake secrets into images.** Build args and `Dockerfile` `ENV` for production secrets leak in layer history; inject at **runtime** (Kubernetes Secret, cloud secret manager → env or mounted file, CI/CD sealed secrets).
- **Do not log secrets.** Avoid printing `os.environ`, full header dicts, or exception messages that echo user-controlled `Authorization` bodies. Use {mod}`fluxlit.logging.redact` when copying headers into logs or debug output.
- **Scope secrets to the process that needs them.** Long-lived **IdP client secrets** belong in the **FastAPI** / gateway environment, not in patterns that expose them to untrusted Streamlit widgets (see {doc}`security`).

## Kubernetes and cloud patterns

- **Kubernetes:** mount **`Secret`** as files under `/var/run/secrets/...` or map keys to **env vars** on the Pod; use **`envFrom`** only where every key is intended for the container. Prefer **workload identity** (IAM, GCP SA) for fetching short-lived tokens over long-lived API keys in env.
- **AWS / GCP / Azure:** use the platform secret store and inject into the task at rollout; rotate by **new secret version + rolling restart** rather than editing running pods in place.
- **Local / dev:** `.env` is fine for developer machines; keep **`.env` out of Docker context** (the default `.dockerignore` from `fluxlit build` already lists `.env`).

## Logs and observability

Gateway access logs and custom middleware can accidentally record **`Authorization`**, cookies, or API keys. When building structured logs:

- Prefer **allowlists** of field names; never dump `request.headers` wholesale into production indexes.
- Use {mod}`fluxlit.logging.redact` helpers when you must log a **subset** of headers for support.

See {doc}`observability` for JSON formatter examples and correlation IDs.

## JWT and OIDC secret rotation

### HS256 (shared secret)

Used when validation uses a single symmetric key (e.g. **`FLUXLIT_JWT_HS256_SECRET`** or your own {class}`~fluxlit.auth.jwt.JWTAuthConfig`).

1. **Generate** a new strong secret; keep the old one available during overlap if you need **zero-downtime** acceptance of tokens signed with either key (requires app support for multiple secrets—not the default single-env configuration).
2. **Simplest safe rollout:** schedule a short window; deploy the new secret; **invalidate** outstanding access tokens if TTL allows, or accept that old tokens fail until they expire.
3. **Roll pods** after changing env so every process reads the new value; verify **`/api/...`** protected routes with a token minted after rotation.

### JWKS (asymmetric / IdP keys)

When using **`FLUXLIT_JWT_JWKS_URL`** (or an equivalent URL in {class}`~fluxlit.auth.jwt.JWTAuthConfig`), verification keys come from the IdP.

1. **IdP key rotation** is controlled by the issuer: new keys appear in JWKS with a new **`kid`**; old keys remain until signing stops.
2. FluxLit’s JWT path fetches JWKS as configured—ensure **network egress** to the JWKS URL from the gateway and watch **cache / TTL** behavior if you customize HTTP clients; after IdP rotation, stale caches can cause **short 401 bursts** until refreshed.
3. **OIDC client secret** rotation: update the secret at the IdP, then update **`OIDC_CLIENT_SECRET`** (or your env) and **roll** replicas so Streamlit child processes inherit the new env.

### BFF signing secrets

**`FLUXLIT_OIDC_BFF_SECRET`** (and similar) protect cookies or server-side exchanges. Rotate like HS256: deploy new value, roll processes, coordinate with any **sticky session** or **multiple replica** constraints documented in {doc}`security`.

For recipe-level wiring, see {doc}`auth-recipes`.
