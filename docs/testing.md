# Testing

FluxLit is tested with **pytest**, **Ruff**, and **mypy** (strict). Application tests can use the same tools you use for FastAPI and Streamlit.

## Gateway-level API tests

Prefer {class}`~fluxlit.testing.FluxLitTestClient` so requests go through the **gateway** with the real API prefix and `/healthz` behavior:

```python
from fluxlit import FluxLit, FluxLitTestClient

app = FluxLit(title="Test")
client = FluxLitTestClient(app)

assert client.api_get("/healthz").status_code == 200
```

## Streamlit UI tests

Where your Streamlit version supports it, use **`streamlit.testing.v1.AppTest`**. {class}`~fluxlit.testing.FluxLitTestClient` exposes {meth}`~fluxlit.testing.FluxLitTestClient.streamlit` to run FluxLit’s Streamlit entrypoint:

```python
at = client.streamlit(target="my_app:app", extra_sys_path=".")
```

## Plain Starlette TestClient

You can also point `starlette.testclient.TestClient` at the ASGI gateway built with {func}`~fluxlit.gateway.build_gateway` if you need lower-level control.
