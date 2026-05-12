# Cookbook

Short, copy-paste patterns for common FluxLit deployments and tests. For narrative guides,
see the {doc}`index` table of contents.

## Forward-auth style header for a Streamlit page

Use {class}`~fluxlit.pages.di.Header` with an explicit map from trusted code (or tests):

```python
from typing import Annotated, Any

from fluxlit import FluxLit
from fluxlit.client import ApiClient
from fluxlit.pages.di import Header, set_page_header_context, reset_page_header_context

app = FluxLit(title="Example")


@app.page("/")
def home(st: Any, client: ApiClient, remote_user: Annotated[str | None, Header("x-remote-user")]) -> None:
    st.write(remote_user or "anonymous")
```

In production, set the map from middleware or a FastAPI dependency that runs in the
Streamlit process—not from untrusted client input without validation.

## Optional ``traceparent`` on the Streamlit HTTP hop

When you need OpenTelemetry correlation inside Streamlit without custom hooks, allowlist
non-secret headers (see ``FLUXLIT_GATEWAY_FORWARD_CLIENT_HEADERS_TO_STREAMLIT`` in
{doc}`configuration`):

```bash
export FLUXLIT_GATEWAY_FORWARD_CLIENT_HEADERS_TO_STREAMLIT='["traceparent"]'
```

Then read them with ``st.context.headers`` or ``Annotated[..., Header("traceparent")]``.

## Multipage + URL session continuity

Pair {doc}`url-session` with {doc}`deep-links`: preserve the same ``fluxlit_sid`` (or your
configured query param) when building ``st.navigation`` links so refresh on any page
reloads the same server-side blob.

## ``FluxLitTestClient`` with ``Depends`` overrides

Use ``page_overrides`` (or ``FLUXLIT_TEST_PAGE_OVERRIDES``) to inject fake dependencies in
AppTest—see {doc}`testing` and ``page_overrides`` in the Streamlit testing section.

## Production pins (``uv`` / ``pip-tools``)

See {doc}`support-matrix` for supported Python and Streamlit ranges and a minimal
constraints example you can drop into CI or Docker builds.
