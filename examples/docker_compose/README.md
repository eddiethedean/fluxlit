# FluxLit Docker Compose example

Minimal **FastAPI + Streamlit** app served on port **8000** inside the container.

## Build and run

From this directory:

```bash
docker compose up --build
```

Check health and readiness:

```bash
curl -sS http://127.0.0.1:8000/api/healthz
curl -sS http://127.0.0.1:8000/api/readyz
```

Open **http://127.0.0.1:8000/** in a browser.

## Notes

- **Locked dependencies:** `requirements.txt` is generated from `requirements.in` with **`uv pip compile`** or **`pip-compile`** (`pip-tools`). Regenerate after each FluxLit PyPI release (or when refreshing transitive pins); the lock pins ``fluxlit`` to the example line in that file.
- The `Dockerfile` installs from that lockfile. To test against a local checkout instead, replace the install step with a `COPY` of your wheel or an editable install.
- For **nginx / TLS / subpath** deployments, see [docker/proxy-deployment/README.md](../../docker/proxy-deployment/README.md).
- **Logs:** set **`FLUXLIT_ENABLE_GATEWAY_ACCESS_LOG=1`** for structured gateway lines; for one JSON object per line, configure `logging` with **`fluxlit.logging.JsonLogFormatter`** (see [Observability](https://fluxlit.readthedocs.io/en/stable/observability.html) on Read the Docs). **`FLUXLIT_ENABLE_REQUEST_LOGGING=1`** logs the inner FastAPI app only.
- **Gateway limits:** upstream timeouts, max proxied body size (**413**), concurrent upstream HTTP cap, `httpx` pool limits, and WebSocket tuning use **`FLUXLIT_GATEWAY_*`** variables — see [Configuration](https://fluxlit.readthedocs.io/en/stable/configuration.html#environment-variables).
