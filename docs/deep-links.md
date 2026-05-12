# Deep links and query parameters

FluxLit serves the **Streamlit shell** on the public app base (respecting
`FLUXLIT_ROOT_PATH` / `FLUXLIT_STREAMLIT_PUBLIC_PATH`) and the **API** under
`FLUXLIT_API_MOUNT_PATH` (default `/api`). Email links, invite flows, and
password-reset entrypoints should point at the **Streamlit** URL with query
parameters, not at POST-only API routes.

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
import streamlit as st
from fluxlit import query_params

params = query_params(st)
token = params.get("token", "")
```

## Optional `?page=` routing

When you send users to the app root with a **page title** or path segment in the
query string, {func}`fluxlit.match_nav_page` resolves it against
{attr}`~fluxlit.app.FluxLit.pages` (``path``, ``title``, handler):

```python
from fluxlit import match_nav_page, query_params

params = query_params(st)
hit = match_nav_page(params, app.pages, page_key="page")
if hit:
    path, title = hit
    # drive your own UI (e.g. default widget values) from path/title
```

Matching order: exact **title**, exact **path**, Streamlit-style **slug** (``"/"`` →
``"home"``), then path segments with slashes stripped from **both** sides (so
``reports/`` can match ``/reports``).

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
as in production.

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
