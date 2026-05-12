# Deep links and query parameters

FluxLit serves the **Streamlit shell** on the public app base (respecting
`FLUXLIT_ROOT_PATH` / `FLUXLIT_STREAMLIT_PUBLIC_PATH`) and the **API** under
`FLUXLIT_API_MOUNT_PATH` (default `/api`). Email links, invite flows, and
password-reset entrypoints should point at the **Streamlit** URL with query
parameters, not at POST-only API routes. For **security** when those parameters
carry session or reset tokens, read {doc}`url-session-token-security`.

## Build links from FastAPI

Use {attr}`~fluxlit.app.FluxLit.urls` with the current {class}`starlette.requests.Request`
so links match subpaths and `FLUXLIT_PUBLIC_BASE_URL`:

```python
from fastapi import FastAPI, Request

app = FastAPI()
# ... attach your FluxLit instance as ``fl`` ...

@app.get("/internal/invite-link")
def invite_link(request: Request, token: str) -> dict[str, str]:
    return {
        "ui": fl.urls.page_url(
            request,
            "/",
            query={"page": "Accept invite", "token": token},
        ),
    }
```

{meth}`~fluxlit.application.public_urls.FluxLitPublicUrls.page_url` is an alias for
{meth}`~fluxlit.application.public_urls.FluxLitPublicUrls.for_page`; both append the
configured public mount and percent-encode query values.

## Read query parameters in Streamlit

{func}`fluxlit.query_params` normalizes ``st.query_params`` to a ``dict[str, str]``,
using the **first** value when Streamlit exposes a list (multiple values for one key):

```python
from typing import Any

import streamlit as st
from fluxlit import query_params

def show_token(st: Any) -> None:
    params = query_params(st)
    token = params.get("token", "")
```

For **Pydantic-validated** query models (single keys, defaults, coercion), use
{func}`~fluxlit.pages.query.parse_query_params` — see {doc}`streamlit-pages-typing`.

## Optional `?page=` routing

When you send users to the app root with a **page title** or path segment in the
query string, {func}`fluxlit.match_nav_page` resolves against a **sequence of pages**
(``(path, title, handler)`` tuples, :class:`~fluxlit.pages.records.PageRecord` instances,
or similar duck-typed rows). The unified Streamlit entrypoint (:mod:`fluxlit.streamlit.main`)
passes the **same ordered** :attr:`~fluxlit.app.FluxLit.page_records` list it uses to build
``st.navigation`` (including :meth:`~fluxlit.app.FluxLit.navigation` sort when
``NavigationModel.order`` is set), **not** the raw :attr:`~fluxlit.app.FluxLit.pages` tuple
view, so ``?page=`` tie-breaking follows the **sidebar order** you see in the UI.

You can still call {func}`fluxlit.match_nav_page` yourself when you need custom logic
beyond navigation:

```python
from typing import Any

from fluxlit import match_nav_page, query_params
from fluxlit.app import FluxLit
from fluxlit.client import ApiClient


def apply_deep_link(st: Any, client: ApiClient, fl: FluxLit) -> None:
    _ = client
    params = query_params(st)
    hit = match_nav_page(params, list(fl.page_records), page_key="page")
    if hit:
        path, title = hit
        # drive your own UI (e.g. default widget values) from path/title
```

If you call {func}`fluxlit.match_nav_page` yourself, pass the **same** ordered
``list[PageRecord]`` the entrypoint would use (after optional
:meth:`~fluxlit.app.FluxLit.navigation` sorting via
:func:`~fluxlit.streamlit.nav_order.navigation_sort_key`), not ``fl.pages``, so
ordering matches the sidebar and ``?page=`` resolution.

Matching order: exact **title**, exact **path**, Streamlit-style **slug** (``"/"`` →
``"home"``), then path segments with slashes stripped from **both** sides (so
``reports/`` can match ``/reports``).

The entrypoint also applies ``PageMeta.children`` for sidebar ordering (see
:mod:`fluxlit.streamlit.nav_build`). If those edges contain a **cycle**, FluxLit emits a
``UserWarning`` and falls back to appending unresolved pages in registration order.

## Security: tokens and PII in URLs

Anything in the query string can leak via:

- **Referer** headers when users follow outbound links to other sites.
- **Browser history**, shared screenshots, and shoulder-surfing.
- **Access logs** and crash reports unless values are redacted (FluxLit’s gateway
  can redact configured session query keys; see {doc}`observability` and
  {doc}`url-session`).

Prefer **short-lived**, **single-use** tokens, **HTTPS** everywhere, and
**clearing** sensitive query keys after read (where Streamlit allows) once you
have copied values into `st.session_state`. For durable state across reloads
without putting secrets in the URL, consider {doc}`url-session` patterns instead.

## Testing with `FluxLitTestClient` and `AppTest`

**API routes** that return `page_url` should be exercised through
{class}`~fluxlit.testing.FluxLitTestClient` so the same gateway prefix rules apply
as in production. You can also pass ``query_params=`` to
:meth:`~fluxlit.testing.FluxLitTestClient.streamlit` instead of mutating ``AppTest``
manually.

For **Streamlit** `AppTest`, set query values on the runner **before** `run()`:

```python
from streamlit.testing.v1 import AppTest
from fluxlit import query_params
import textwrap

script = textwrap.dedent(
    '''
    import streamlit as st
    from fluxlit import query_params

    p = query_params(st)
    st.text_input("Token", value=p.get("token", ""), key="tok")
    '''
)
at = AppTest.from_string(script, default_timeout=10)
at.query_params["token"] = "from-email"
at.run()
assert at.text_input(key="tok").value == "from-email"
```

See also {doc}`testing` for `FLUXLIT_TESTS`, multipage smoke tests, and
`streamlit_main_path()`.
