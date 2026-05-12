# External URL session stores

These examples implement `fluxlit.url_session.SessionStore` outside FluxLit core.

Run the SQLite demo from the repository root:

```bash
fluxlit run examples.session_stores.app:app --no-pidfile
```

The page writes refresh-continuity state into `fluxlit-sessions.sqlite3` by
default. It uses {func}`fluxlit.url_session.hydrate_url_session_typed` with a
small Pydantic model (`UrlSessionPayload`) so the store blob is validated like
other **0.9+** typed helpers. Override with:

```bash
FLUXLIT_SESSION_SQLITE_PATH=/tmp/fluxlit-sessions.sqlite3 \
  fluxlit run examples.session_stores.app:app --no-pidfile
```

`redis_store.py` is intentionally dependency-free: pass a `redis.Redis` client, or
any compatible object with `get`, `set`, `setex`, and `delete`.
