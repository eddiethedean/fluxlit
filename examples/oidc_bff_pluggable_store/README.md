# OIDC BFF: pluggable token store (multi-replica)

The BFF routes registered by `fluxlit.auth.oidc.register_oidc_bff_routes` must correlate:

1. **PKCE** — OAuth `state` → `code_verifier` between `/auth/login` and `/auth/callback`.
2. **One-time exchange** — short-lived `auth_code` query param → first-party JWT at `/auth/exchange`.

Implement `fluxlit.auth.oidc.OIDCBFFTokenStore` and pass it as `OIDCBFFConfig.bff_token_store`. The default is `InMemoryOIDCBFFTokenStore`, which is correct for a single API worker.

For **multiple FastAPI replicas** behind a load balancer, use a shared backend (typically **Redis**) so any replica can validate `state` and redeem `auth_code`. Sketch:

```python
# Pseudocode: redis.asyncio with SET key value EX ttl
class RedisOIDCBFFTokenStore:
    def save_pkce_verifier(self, state: str, code_verifier: str, *, now: float) -> None:
        ...

    def pop_pkce_verifier(self, state: str, *, now: float) -> str | None:
        ...

    def save_exchange_token(self, auth_code: str, access_token: str, *, now: float) -> None:
        ...

    def pop_exchange_token(self, auth_code: str, *, now: float) -> str | None:
        ...
```

Use distinct key prefixes for PKCE vs exchange payloads, set TTLs to match `state_ttl_seconds` and `otc_ttl_seconds` on `OIDCBFFConfig`, and treat values as opaque secrets at rest.

See also `SECURITY.md` (OIDC BFF section) and `docs/auth-recipes.md`.
