"""Optional no-dependency tracing hooks for FluxLit internals.

The core package does not depend on OpenTelemetry. Integrations can register a
small context-manager factory and translate FluxLit spans into any tracing backend.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager, nullcontext
from contextvars import ContextVar, Token
from typing import TypeAlias

TraceValue: TypeAlias = str | int | float | bool | None
TraceAttributes: TypeAlias = Mapping[str, TraceValue]
TraceHook: TypeAlias = Callable[[str, TraceAttributes], AbstractContextManager[None]]

_trace_hook: ContextVar[TraceHook | None] = ContextVar("fluxlit_trace_hook", default=None)


def set_trace_hook(hook: TraceHook | None) -> Token[TraceHook | None]:
    """Install a tracing hook for the current context and return a reset token."""
    return _trace_hook.set(hook)


def reset_trace_hook(token: Token[TraceHook | None]) -> None:
    """Reset the tracing hook installed by :func:`set_trace_hook`."""
    _trace_hook.reset(token)


def trace_span(name: str, attributes: TraceAttributes) -> AbstractContextManager[None]:
    """Return a context manager for an optional span.

    If no hook is installed, this is a no-op. Hook exceptions intentionally bubble
    up so integrations fail loudly during development instead of hiding broken
    instrumentation.
    """
    hook = _trace_hook.get()
    if hook is None:
        return nullcontext()
    return hook(name, attributes)
