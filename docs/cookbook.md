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

## Gateway Prometheus metrics

Install the optional extra, enable metrics, and scrape the **gateway** process (not Streamlit):

```bash
pip install "fluxlit[metrics]"
export FLUXLIT_ENABLE_GATEWAY_PROMETHEUS_METRICS=1
# Optional: custom path (must not start with your API mount, default /api)
# export FLUXLIT_GATEWAY_PROMETHEUS_METRICS_PATH=/__fluxlit/metrics
fluxlit run app:app
```

Scrape ``GET http://<gateway-host>:<port>/__fluxlit/metrics`` (or your overridden path). When
``FLUXLIT_ROOT_PATH`` is set, prefix that path for browsers; scrapers inside the same network
often hit the gateway bind directly without the public prefix—see {doc}`observability` for RED
names and cardinality notes.

## Kubernetes-style probes (minimal)

Liveness does **not** wait for Streamlit; readiness does when the unified runtime manages the
sidecar. Paths below assume default ``api_mount_path=/api`` at the **gateway** origin (add your
``root_path`` / ingress prefix for external checks):

```yaml
livenessProbe:
  httpGet:
    path: /api/healthz
    port: 8000
readinessProbe:
  httpGet:
    path: /api/readyz
    port: 8000
```

Narrative, timeouts, and graceful shutdown: {doc}`deployment`.

## Fail CI on configuration warnings

After exporting the same ``FLUXLIT_*`` values your container will use:

```bash
fluxlit config app:app --strict
```

Exit code **1** if any warning is emitted (errors always fail). See {doc}`cli` for ``--json``
and redacted settings.

## Cap uploads proxied to Streamlit (``413``)

The gateway enforces a max **incoming** body size on the HTTP hop to Streamlit (responses are
handled separately—see gateway notes in {doc}`configuration`). Example **64 MiB**:

```bash
export FLUXLIT_GATEWAY_MAX_PROXY_REQUEST_BODY_BYTES=67108864
```

When a request exceeds the limit, clients receive **413**. The Docker proxy smoke image sets a
small limit to assert this path; tune per app.
