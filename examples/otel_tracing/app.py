"""FluxLit app showing how to bridge trace hooks to OpenTelemetry."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from fluxlit import FluxLit, set_trace_hook
from fluxlit.client import ApiClient
from fluxlit.tracing import TraceAttributes

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
except ImportError as exc:  # pragma: no cover - example import guard
    raise RuntimeError(
        "Install the example dependencies: pip install -r examples/otel_tracing/requirements.txt"
    ) from exc

provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("fluxlit-example")


@contextmanager
def otel_trace_hook(name: str, attributes: TraceAttributes) -> Iterator[None]:
    with tracer.start_as_current_span(name) as span:
        for key, value in attributes.items():
            if value is not None:
                span.set_attribute(key, value)
        yield


set_trace_hook(otel_trace_hook)

app = FluxLit(title="FluxLit OpenTelemetry Demo")


@app.api.get("/hello")
def hello() -> dict[str, str]:
    return {"message": "hello from traced FluxLit"}


@app.page("/", title="Tracing")
def home(st: Any, client: ApiClient) -> None:
    st.title("FluxLit OpenTelemetry Demo")
    st.write(client.get("/hello").json())
