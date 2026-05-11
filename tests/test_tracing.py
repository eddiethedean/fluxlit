from __future__ import annotations

from contextlib import contextmanager

import pytest

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


def test_trace_hook_reset_restores_previous_hook() -> None:
    seen: list[str] = []

    @contextmanager
    def first(name: str, attrs):
        seen.append(f"first:{name}")
        yield

    @contextmanager
    def second(name: str, attrs):
        seen.append(f"second:{name}")
        yield

    token_first = set_trace_hook(first)
    try:
        token_second = set_trace_hook(second)
        try:
            with trace_span("during", {}):
                pass
        finally:
            reset_trace_hook(token_second)
        with trace_span("after", {}):
            pass
    finally:
        reset_trace_hook(token_first)

    assert seen == ["second:during", "first:after"]


def test_trace_hook_exceptions_bubble() -> None:
    @contextmanager
    def hook(name: str, attrs):
        raise RuntimeError("trace failed")
        yield

    token = set_trace_hook(hook)
    try:
        with pytest.raises(RuntimeError, match="trace failed"):
            with trace_span("broken", {}):
                pass
    finally:
        reset_trace_hook(token)
