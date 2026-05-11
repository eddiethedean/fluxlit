from __future__ import annotations

from contextlib import contextmanager

from fluxlit import reset_trace_hook, set_trace_hook, trace_span


def test_trace_span_noop_without_hook() -> None:
    with trace_span("test.span", {"key": "value"}):
        pass


def test_trace_hook_receives_span_name_and_attributes() -> None:
    seen: list[tuple[str, dict[str, object]]] = []

    @contextmanager
    def hook(name: str, attrs):
        seen.append((name, dict(attrs)))
        yield

    token = set_trace_hook(hook)
    try:
        with trace_span("test.span", {"key": "value", "count": 1}):
            pass
    finally:
        reset_trace_hook(token)

    assert seen == [("test.span", {"key": "value", "count": 1})]
