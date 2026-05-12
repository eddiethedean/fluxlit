# URL sessions, query tokens, and email links (security)

**Why read this:** FluxLit’s {doc}`url-session` helpers and many product flows put **opaque identifiers in the query string**. Query data also appears in **invite links**, **password resets**, and **deep links** ({doc}`deep-links`). This page separates **URL-session continuity** from **application authentication**, describes leak surfaces, and aligns logging and debug behavior with {doc}`secrets` and {doc}`observability`.

## URL session ID vs application auth tokens

These solve different problems. Do **not** treat them as interchangeable.

| Concept | Typical role | Lifetime | Carried in URL? |
|---------|--------------|----------|-----------------|
| **URL session id** (`fluxlit_sid` by default) | Opaque key for a **server-side** {class}`~fluxlit.url_session.SessionStore` blob so a **full page reload** can rehydrate `st.session_state` without cookies. | Short; rotate after privilege changes. Server store is the source of truth. | **Yes** — by design for this feature. |
| **Access JWT / API bearer** | Proves identity to **FastAPI** (`Authorization` header from {doc}`streamlit-api-client` patterns). | Short (minutes). | **Avoid** putting bearer JWTs in query strings in production (see below). |
| **Refresh token / IdP secrets** | Long-lived or high-value secrets. | Controlled by your IdP / BFF. | **Never** in URLs, logs, or `st.write`. |

URL-session ids are **bearer secrets** relative to your store: anyone who obtains the link can impersonate that **hydrated UI session** until the id expires or is deleted. They are **not** a substitute for API-level authorization; keep enforcing roles on `/api` routes.

## Avoid long-lived JWTs in URLs

Putting a **JWT** (or any long-lived signed blob) in a query parameter is risky:

- **Browser history** and synced devices retain URLs.
- **Reverse proxies**, CDNs, and application **access logs** may record query strings unless explicitly stripped.
- **Referer** headers can leak full URLs to third-party origins unless you tighten policy (below).
- **Screenshots** and shared links spread tokens accidentally.

**Prefer:** exchange **short-lived opaque tokens** (random ids) over **HTTPS** in the link; validate server-side in FastAPI or Streamlit; then issue cookies or session state through **server-side** code paths (see {doc}`auth-recipes` BFF patterns). If you must pass a JWT once in a query for legacy reasons, treat it as **single-use**, **very short TTL**, and rotate immediately after consumption.

## Email, invite, and password-reset links

Use the same discipline as magic links industry-wide:

1. **Opaque random token** (high entropy, stored hashed server-side if persisted).
2. **Short TTL** (e.g. 15–60 minutes for invites; tighter for password reset).
3. **One-time use** where the threat model requires it (invalidate or delete the row on success).
4. **HTTPS only** at the public edge ({doc}`production-tls`).
5. **Narrow scope:** token authorizes only the intended action (accept invite, set password), not broad API access.

Example shape (conceptual — your app owns storage and routes):

```text
GET https://app.example.com/content/app/?page=Reset+password&reset=opaque_128_bit_random
```

The value of `reset=` is **not** a JWT; it is a lookup key. After validation, perform the reset **server-side** and redirect to a clean URL **without** the token.

## Referrer-Policy and outbound links

When the URL bar contains sensitive query keys, tighten what browsers send on navigation:

- Prefer **`Referrer-Policy: strict-origin-when-cross-origin`** (or stricter) at the edge or via {attr}`~fluxlit.config.FluxlitSettings.enable_security_headers` where appropriate.
- For pages that display highly sensitive material, consider **`no-referrer`** for that response (tradeoff: some analytics break).

FluxLit cannot remove tokens from the user’s address bar; **policy + TTL + opaque tokens** reduce blast radius.

## Logging and redaction

- **Gateway access logs:** when structured logging is enabled, the `query` field **redacts** the configured URL-session key (`fluxlit_sid` by default and {attr}`~fluxlit.config.FluxlitSettings.url_session_query_param`). See {doc}`observability`.
- **Custom logs:** never print full URLs at INFO when they may contain reset or session tokens. Use {mod}`fluxlit.logging.redact` and allowlists; follow {doc}`secrets`.
- **Debug mode:** `FLUXLIT_DEBUG` / `fluxlit dev --debug` enables richer diagnostics and `GET /__fluxlit/debug`; responses use **redacted** settings snapshots. Debug does **not** disable redaction in gateway access logs — it adds correlation (request ids, path-split lines), not raw secrets. See {doc}`configuration` and {doc}`troubleshooting` (debug section).

## Request IDs vs secrets

**Request IDs** (`X-Request-ID`) help join gateway, API, and Streamlit lines in support tickets. They are **not** authentication and must not replace auth headers. Propagation from {meth}`fluxlit.app.FluxLit.get_client` in debug mode is for **correlation**, not for exposing tokens.

## Related reading

- {doc}`url-session` — API for `ensure_url_session` / `hydrate_url_session` / `persist_url_session`
- {doc}`deep-links` — building and parsing `page_url` / `query_params`
- {doc}`security` — threat model and where tokens should live
- {doc}`secrets` — rotation and log hygiene
- {doc}`production-tls` — TLS, HSTS, forwarded headers
