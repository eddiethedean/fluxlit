# URL session continuity (no cookies)

**Goal:** keep **application** state across a **full browser reload** (F5) without using the browser **cookie** jar.

Streamlit’s default `st.session_state` is tied to the live script session; a hard refresh often starts a new session. FluxLit exposes small helpers in {mod}`fluxlit.url_session`: an **opaque query parameter** (default `fluxlit_sid`) plus a **server-side** {class}`~fluxlit.url_session.SessionStore`.

## Quick pattern

```python
import streamlit as st
from fluxlit.url_session import (
    InMemorySessionStore,
    ensure_url_session,
    hydrate_url_session,
    persist_url_session,
)

# Single-process dev only — use Redis (or similar) in multi-worker / multi-replica prod.
if "_fluxlit_store" not in st.session_state:
    st.session_state["_fluxlit_store"] = InMemorySessionStore()

store = st.session_state["_fluxlit_store"]
ensure_url_session(st, store)
hydrate_url_session(st, store)

# ... your app mutates st.session_state ...

persist_url_session(st, store)
```

Call **`hydrate_url_session` early** each run, then **`persist_url_session`** when values you care about change (or at the end of the run). The default **merge** policy uses `session_state.setdefault` so existing widget keys are not overwritten by stale store data on the first paint.

## Multipage / `st.navigation`

Treat the query string as part of your **public URL contract**. Any link or `st.switch_page` target should **preserve** the same `fluxlit_sid` (or your configured name) so refresh on any page still resolves the same server-side blob.

## Configuration

{class}`~fluxlit.config.FluxlitSettings.url_session_query_param` (env: `FLUXLIT_URL_SESSION_QUERY_PARAM`) names the query key for your app and for **gateway access log redaction** (see {doc}`observability`). Helpers accept an explicit `param=` argument if you prefer not to read settings in Streamlit.

## Security

- **HTTPS** in production: the token is effectively a **bearer secret** in the URL (bookmarks, `Referer`, shared links, screenshots).
- **TTL:** {class}`~fluxlit.url_session.InMemorySessionStore` supports TTL; cap size with `max_entries`.
- **Logging:** do not log raw tokens at INFO. The gateway structured log field `query` redacts `fluxlit_sid` and your configured `url_session_query_param`.

## External store recipes

For multiple replicas, implement {class}`~fluxlit.url_session.SessionStore` with a
shared backend. Keep the implementation in your app or infrastructure package so
FluxLit core does not need to depend on Redis, SQL drivers, or cloud SDKs.

Runnable examples live in `examples/session_stores/`:

```bash
fluxlit run examples.session_stores.app:app --no-pidfile
```

The demo uses the stdlib SQLite store by default. Set
`FLUXLIT_SESSION_SQLITE_PATH` to choose the database file.

```python
import json
from typing import Any

from fluxlit.config import JsonValue
from fluxlit.url_session import SessionStore


class RedisSessionStore(SessionStore):
    def __init__(self, redis_client: Any, *, prefix: str = "fluxlit:sid:") -> None:
        self.redis = redis_client
        self.prefix = prefix

    def _key(self, session_id: str) -> str:
        return f"{self.prefix}{session_id}"

    def get(self, session_id: str) -> dict[str, JsonValue] | None:
        raw = self.redis.get(self._key(session_id))
        if raw is None:
            return None
        return json.loads(raw)

    def set(
        self,
        session_id: str,
        data: dict[str, JsonValue],
        *,
        ttl_seconds: float | None = None,
    ) -> None:
        payload = json.dumps(data)
        if ttl_seconds is None:
            self.redis.set(self._key(session_id), payload)
        else:
            self.redis.setex(self._key(session_id), int(ttl_seconds), payload)

    def delete(self, session_id: str) -> None:
        self.redis.delete(self._key(session_id))
```

Production notes:

- Use a TTL and rotate session IDs after privilege changes.
- Keep the URL token opaque; never encode user identity or permissions in it.
- Add monitoring for store latency and errors because page hydration now depends on it.
- Pair the shared store with rollout/drain guidance in {doc}`deployment`; sticky sessions alone do not protect users when a replica restarts.

## Related

- Roadmap **Phase 2 follow-on** in {doc}`roadmap`.
- Architecture note in `PLAN.md` (“Browser refresh and session continuity”).
