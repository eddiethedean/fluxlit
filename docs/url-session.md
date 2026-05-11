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

## Related

- Roadmap **Phase 2 follow-on** in {doc}`roadmap`.
- Architecture note in `PLAN.md` (“Browser refresh and session continuity”).
