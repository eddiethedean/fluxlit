# Streamlit pages: typing, `Depends`, and manifests

FluxLit **0.9** adds optional **FastAPI-like** patterns for Streamlit page handlers while
keeping the default ``(st, client) -> None`` contract unchanged.

## Registration

Use {meth}`~fluxlit.app.FluxLit.page` as today, with optional metadata:

- ``icon`` — forwarded to {class}`streamlit.navigation` / ``st.Page`` where supported.
- ``tags`` — labels for {meth}`~fluxlit.app.FluxLit.build_page_manifest`.
- ``page_meta`` — static {class}`~fluxlit.pages.meta.PageMeta` (for example ``page_icon``)
  merged into ``st.Page`` where Streamlit accepts it. Global
  ``streamlit.set_page_config`` still runs once at entry; per-run layout overrides are
  limited by Streamlit’s “first command” rule—see {class}`~fluxlit.pages.meta.PageMeta`.

Full records are available as {attr}`~fluxlit.app.FluxLit.page_records`; {attr}`~fluxlit.app.FluxLit.pages`
remains a list of ``(path, title, handler)`` tuples for backward compatibility.

## ``PageMeta`` vs ``set_page_config`` vs ``st.Page``

Streamlit only guarantees ``streamlit.set_page_config`` **before any other Streamlit command**
on a run. FluxLit calls global ``set_page_config`` once from the Streamlit entrypoint using
:class:`~fluxlit.config.FluxlitSettings` (``title`` and ``streamlit_page_config``). Per-page
:class:`~fluxlit.pages.meta.PageMeta` is applied in two different ways:

| Field | ``@app.page(..., page_meta=…)`` (static, start of run) | Returned ``PageMeta`` (after handler) | ``st.Page`` / sidebar |
| --- | --- | --- | --- |
| ``page_title``, ``page_icon``, ``layout``, ``initial_sidebar_state`` | Merged into ``set_page_config`` **when** those keys are present (must be first commands; FluxLit applies static ``page_meta`` before running the page). | Same keys are **best-effort** via ``set_page_config`` only if Streamlit still allows it; otherwise they are **no-ops** at runtime. | ``page_icon`` may also feed ``st.Page(icon=…)`` when building multipage nav (see entrypoint). |
| ``breadcrumb`` | Ignored until the handler runs. | Sidebar caption via ``st.sidebar.caption``. | — |
| ``order``, ``description``, ``children`` | Used for **manifest / nav ordering** (``children`` merges with registered pages; see below), not Streamlit layout APIs. | Same as static if returned and validated. | ``children`` influences multipage **order** and per-slug **title/icon** overrides in the entrypoint. |

Official Streamlit multipage and ``set_page_config`` behaviour is described in the
`Streamlit multipage apps <https://docs.streamlit.io/develop/concepts/multipage-apps>`_ and
`st.set_page_config <https://docs.streamlit.io/develop/api-reference/configuration/st.set_page_config>`_
documentation.

## Dependency injection

Import {class}`~fluxlit.pages.di.Depends`, {class}`~fluxlit.pages.di.Header`, and
{class}`~fluxlit.pages.di.Cookie` from ``fluxlit`` (or ``fluxlit.pages``).

- **Built-ins:** ``st``, ``client``, {class}`~fluxlit.app.FluxLit`, {class}`~fluxlit.config.FluxlitSettings`,
  {class}`~fluxlit.application.public_urls.FluxLitPublicUrls`, {class}`~fluxlit.client.ApiClient`.
- **Session store:** pass ``session_store=...`` to {class}`~fluxlit.app.FluxLit` and annotate a parameter
  with {class}`~fluxlit.url_session.SessionStore` to receive the same instance.
- **Depends:** ``def page(st, client, user: Annotated[User, Depends(load_user)]): ...`` where
  ``load_user()`` returns the dependency value. Async callables and awaitable returns are
  supported when ``FLUXLIT_ASYNC_PAGE_DEPENDS=1`` / {attr}`~fluxlit.config.FluxlitSettings.async_page_depends`
  is on: if Streamlit (or another caller) already has an **asyncio** loop on the current thread,
  FluxLit runs the coroutine on a **short-lived side thread** with its own loop (avoiding
  nested-loop errors). Keep async deps **fast** and **thread-safe**; do not assume you are on
  Streamlit’s main thread.
- **Header:** resolved in order: (1) ``FLUXLIT_TEST_PAGE_OVERRIDES`` / test kwargs,
  (2) the map from {func}`~fluxlit.pages.di.set_page_header_context`, (3) when present,
  ``st.context.headers`` from Streamlit (HTTP requests only). The gateway does **not** put
  browser headers into the Streamlit process by default.
- **Cookie:** resolved in order: (1) overrides / ``FLUXLIT_TEST_PAGE_OVERRIDES``, (2)
  {func}`~fluxlit.pages.di.set_page_cookie_context`, (3) ``st.context.cookies`` (Streamlit
  1.30+). Cookie **names** are matched case-insensitively. The gateway does **not** merge
  arbitrary browser cookies onto the internal hop unless your deployment forwards them and
  Streamlit exposes them on ``st.context``.

**Optional HTTP forwarding:** set ``FLUXLIT_GATEWAY_FORWARD_CLIENT_HEADERS_TO_STREAMLIT``
to a comma-separated or JSON list of **lowercase** header names (for example ``traceparent``).
FluxLit copies **only** those names from the browser onto the gateway → Streamlit **HTTP**
hop so ``st.context.headers`` and ``Header()`` can read them. ``authorization``, ``cookie``,
and hop-by-hop / ``X-Forwarded-*`` names are **rejected**. WebSocket requests already forward
most browser headers on a curated path—see :mod:`fluxlit.gateway.websocket_proxy`.

**Explicit bridge:** for sensitive forward-auth patterns, prefer mapping trusted headers into
{func}`~fluxlit.pages.di.set_page_header_context` from code that runs in the Streamlit process,
with strict allowlists and redaction—never log raw ``Authorization`` or session cookies.

**Claims-style models:** use ``Depends`` with a callable that returns a Pydantic model;
pair with your FastAPI JWT stack on the API side—FluxLit does not parse JWTs in Streamlit
unless you supply the callable.

### Async ``Depends`` and header resolution (0.10)

| Situation | Behaviour |
|-----------|-----------|
| Sync ``Depends`` callable | Invoked normally; return value injected. |
| Async / awaitable deps, flag **off** | ``TypeError`` with guidance to set ``FLUXLIT_ASYNC_PAGE_DEPENDS=1``. |
| Async / awaitable deps, flag **on**, **no** running asyncio loop on thread | Resolved via ``anyio.run`` (same as earlier 0.9 behaviour). |
| Async / awaitable deps, flag **on**, **running** loop on thread | Resolved on a **short-lived daemon thread** with its own ``asyncio.run`` so nested-loop errors are avoided. |

Keep async deps idempotent and fast; they must not rely on thread-local state tied to
Streamlit’s main script thread. If resolution exceeds the join limit, FluxLit raises
:class:`TimeoutError`; the daemon thread may still run until the coroutine completes, so
avoid unbounded work in async dependencies.

## Query and session state

- {func}`~fluxlit.pages.query.parse_query_params` builds a Pydantic model from ``st.query_params``
  (with ``strict=True`` in tests to surface {class}`pydantic.ValidationError`).
- {class}`~fluxlit.pages.session_state.SessionModel` maps Pydantic models to ``st.session_state``.
- {func}`~fluxlit.url_session.hydrate_url_session_typed` validates URL-session blobs as a model.

## Navigation order

{meth}`~fluxlit.app.FluxLit.navigation` accepts a {class}`~fluxlit.pages.navigation.NavigationModel`
with an ``order`` tuple of URL paths (``"/"`` slugifies like the Streamlit entrypoint).

Optional ``PageMeta.children`` entries are dictionaries with ``path`` or ``url_path`` (and
optional ``title`` / ``icon``). They **merge** with registered pages: matching slugs pick
up display overrides; listed children are ordered **immediately after** the parent in the
multipage sidebar. Unknown paths emit a **runtime warning** and are skipped for ``st.Page``
(they do not create routes).

## Manifest and CLI

- {meth}`~fluxlit.app.FluxLit.build_page_manifest` returns JSON-serializable metadata
  (``manifest_version`` **1**, ``manifest_stability`` **stable**).
- ``fluxlit pages manifest [--target module:attr]`` prints JSON using project
  config when ``--target`` is omitted.
- ``fluxlit pages validate [--target ...] [--strict]`` exits **0** when the manifest
  is JSON-serializable, there are no **duplicate page paths** or clashing **url_path**
  slugs (e.g. ``/a`` vs ``/a/``), and (if ``strict_page_signatures`` is on, or ``--strict`` is
  passed) every page handler passes strict signature checks; exits **1** with errors
  printed to stdout for CI. Registration-time :meth:`~fluxlit.app.FluxLit.page` rejects
  duplicate paths and slug collisions early.

## Strict registration

Set ``FLUXLIT_STRICT_PAGE_SIGNATURES=1`` or {attr}`~fluxlit.config.FluxlitSettings.strict_page_signatures`
so unknown page parameters raise at **decorator** time.

## Experimental generator pages

When ``FLUXLIT_EXPERIMENTAL_YIELD_PAGES=1``, a **generator** handler runs ``next()`` twice in
one script execution (setup yield, then body). This is **experimental**; prefer plain
functions unless you understand rerun semantics.

Reruns re-execute the whole script: both ``next()`` calls happen again, so generator
state does **not** survive reruns like a session. Do not rely on the generator for
teardown-critical resources unless you understand that **every** rerun repeats setup.
The first yielded value and the final return/second yield may each carry ``PageMeta``
(breadcrumb, etc.); invalid dicts are surfaced with ``st.error`` when validation fails.

## Optional ``st`` typing (Protocol)

:class:`~fluxlit.streamlit.page.PageFn` keeps ``st`` typed as ``typing.Any`` so apps are not
forced to satisfy the full Streamlit surface. For stricter local typing, define a
``typing.Protocol`` with only the members your page uses (e.g. ``title``, ``write``,
``sidebar``) and annotate ``def home(st: MySt, client): ...``. You can also import
``streamlit`` only under ``typing.TYPE_CHECKING`` in shared modules and use string
annotations. FluxLit does not change the default ``PageFn`` generic to avoid widespread
false positives from partial stubs.

## Static typing

{class}`~fluxlit.app.FluxLit` is a {class}`typing.Generic` over your settings type for **static**
checkers, for example ``FluxLit[MySettings]`` with a custom {class}`~fluxlit.config.FluxlitSettings`
subclass.

## See also

- {doc}`testing` — ``FluxLitTestClient.streamlit(..., page_overrides=...)``.
- {doc}`deep-links` — ``match_nav_page`` and ``?page=``.
- {doc}`url-session` — ``SessionStore`` and URL-bound sessions.
