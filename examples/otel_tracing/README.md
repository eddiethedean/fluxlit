# OpenTelemetry tracing hook example

FluxLit core exposes no-dependency tracing hooks. This example bridges those hooks
to OpenTelemetry and prints spans to stdout with the console exporter.

```bash
python -m pip install -e .
python -m pip install -r examples/otel_tracing/requirements.txt
fluxlit run examples.otel_tracing.app:app --no-pidfile
```

Then open `http://127.0.0.1:8000/` or call:

```bash
curl http://127.0.0.1:8000/api/hello
```

Gateway dispatch emits spans named `fluxlit.gateway.request` with attributes such
as `fluxlit.dispatch`, `http.method_or_type`, `url.path`, and `request_id`.
