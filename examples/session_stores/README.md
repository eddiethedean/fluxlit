# External URL session stores

These examples implement `fluxlit.url_session.SessionStore` outside FluxLit core.

Run the SQLite demo from the repository root:

```bash
fluxlit run examples.session_stores.app:app --no-pidfile
```

The page writes refresh-continuity state into `fluxlit-sessions.sqlite3` by
default. Override with:

```bash
FLUXLIT_SESSION_SQLITE_PATH=/tmp/fluxlit-sessions.sqlite3 \
  fluxlit run examples.session_stores.app:app --no-pidfile
```

`redis_store.py` is intentionally dependency-free: pass a `redis.Redis` client, or
any compatible object with `get`, `set`, `setex`, and `delete`.
