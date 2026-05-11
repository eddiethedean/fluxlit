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

- The `Dockerfile` installs **`fluxlit`** from PyPI. To test against a local checkout, replace the `RUN pip install` line with a `COPY` of your wheel or an editable install.
- For **nginx / TLS / subpath** deployments, see [docker/proxy-deployment/README.md](../../docker/proxy-deployment/README.md).
