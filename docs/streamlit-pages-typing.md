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

## Dependency injection

Import {class}`~fluxlit.pages.di.Depends`, {class}`~fluxlit.pages.di.Header`, and
{class}`~fluxlit.pages.di.Cookie` from ``fluxlit`` (or ``fluxlit.pages``).

- **Built-ins:** ``st``, ``client``, {class}`~fluxlit.app.FluxLit`, {class}`~fluxlit.config.FluxlitSettings`,
  {class}`~fluxlit.application.public_urls.FluxLitPublicUrls`, {class}`~fluxlit.client.ApiClient`.
- **Session store:** pass ``session_store=...`` to {class}`~fluxlit.app.FluxLit` and annotate a parameter
  with {class}`~fluxlit.url_session.SessionStore` to receive the same instance.
- **Depends:** ``def page(st, client, user: Annotated[User, Depends(load_user)]): ...`` where
  ``load_user()`` returns the dependency value (sync only in 0.9.0).
- **Header / Cookie:** resolved from test overrides or a header map set with
  {func}`~fluxlit.pages.di.set_page_header_context`. Streamlit children do **not** see
  browser HTTP headers unless your deployment sets this context from a gateway hook.

**Claims-style models:** use ``Depends`` with a callable that returns a Pydantic model;
pair with your FastAPI JWT stack on the API side—FluxLit does not parse JWTs in Streamlit
unless you supply the callable.

## Query and session state

- {func}`~fluxlit.pages.query.parse_query_params` builds a Pydantic model from ``st.query_params``
  (with ``strict=True`` in tests to surface {class}`pydantic.ValidationError`).
- {class}`~fluxlit.pages.session_state.SessionModel` maps Pydantic models to ``st.session_state``.
- {func}`~fluxlit.url_session.hydrate_url_session_typed` validates URL-session blobs as a model.

## Navigation order

{meth}`~fluxlit.app.FluxLit.navigation` accepts a {class}`~fluxlit.pages.navigation.NavigationModel`
with an ``order`` tuple of URL paths (``"/"`` slugifies like the Streamlit entrypoint).

## Manifest and CLI

- {meth}`~fluxlit.app.FluxLit.build_page_manifest` returns JSON-serializable metadata
  (``manifest_version`` **1**, stability **experimental**).
- ``fluxlit pages manifest [--target module:attr]`` prints the same JSON using project
  config when ``--target`` is omitted.

## Strict registration

Set ``FLUXLIT_STRICT_PAGE_SIGNATURES=1`` or {attr}`~fluxlit.config.FluxlitSettings.strict_page_signatures`
so unknown page parameters raise at **decorator** time.

## Experimental generator pages

When ``FLUXLIT_EXPERIMENTAL_YIELD_PAGES=1``, a **generator** handler runs ``next()`` twice in
one script execution (setup yield, then body). This is **experimental**; prefer plain
functions unless you understand rerun semantics.

## Static typing

{class}`~fluxlit.app.FluxLit` is a {class}`typing.Generic` over your settings type for **static**
checkers, for example ``FluxLit[MySettings]`` with a custom {class}`~fluxlit.config.FluxlitSettings`
subclass.

## See also

- {doc}`testing` — ``FluxLitTestClient.streamlit(..., page_overrides=...)``.
- {doc}`deep-links` — ``match_nav_page`` and ``?page=``.
- {doc}`url-session` — ``SessionStore`` and URL-bound sessions.
