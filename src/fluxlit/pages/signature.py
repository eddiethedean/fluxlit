"""Strict registration-time validation for Streamlit page handler signatures."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Annotated, Any, get_args, get_origin, get_type_hints

from fluxlit.application.public_urls import FluxLitPublicUrls
from fluxlit.client import ApiClient
from fluxlit.config import FluxlitSettings
from fluxlit.pages.di import Cookie, Depends, Header
from fluxlit.pages.flags import FluxlitFeatureFlags
from fluxlit.url_session import SessionStore


def _strip_annotated(ann: Any) -> Any:
    if get_origin(ann) is Annotated:
        return get_args(ann)[0]
    return ann


def _depends_with_callable(param: inspect.Parameter, hints: dict[str, Any], name: str) -> bool:
    ann = hints.get(name, param.annotation)
    if get_origin(ann) is Annotated:
        for a in get_args(ann)[1:]:
            if isinstance(a, Depends) and a.dependency is not None:
                return True
    return isinstance(param.default, Depends) and param.default.dependency is not None


def _has_depends_without_callable(
    param: inspect.Parameter,
    hints: dict[str, Any],
    name: str,
) -> bool:
    ann = hints.get(name, param.annotation)
    if get_origin(ann) is Annotated:
        for a in get_args(ann)[1:]:
            if isinstance(a, Depends):
                return a.dependency is None
    if isinstance(param.default, Depends):
        return param.default.dependency is None
    return False


def _has_header_cookie(param: inspect.Parameter, hints: dict[str, Any], name: str) -> bool:
    ann = hints.get(name, param.annotation)
    if get_origin(ann) is Annotated:
        return any(isinstance(a, (Header, Cookie)) for a in get_args(ann)[1:])
    return False


def _is_injectable_type(base: Any) -> bool:
    if not isinstance(base, type):
        return False
    if issubclass(base, FluxlitSettings):
        return True
    if issubclass(base, FluxLitPublicUrls):
        return True
    if issubclass(base, ApiClient):
        return True
    if base is SessionStore:
        return True
    if base is FluxlitFeatureFlags:
        return True
    from fluxlit.app import FluxLit

    try:
        return issubclass(base, FluxLit)
    except TypeError:  # pragma: no cover
        return False


def validate_strict_page_signature(fn: Callable[..., Any]) -> None:
    """Raise ``TypeError`` if *fn* uses unsupported parameter kinds or unknown injections."""
    sig = inspect.signature(fn)
    globalns = getattr(fn, "__globals__", None) or {}
    qn = getattr(fn, "__qualname__", repr(fn))
    try:
        hints = get_type_hints(fn, globalns=globalns, include_extras=True)
    except NameError as e:
        msg = (
            f"Could not resolve annotations for page handler {qn!r}: {e}. "
            "Fix missing imports, use ``from __future__ import annotations``, or replace "
            "forward references with concrete types when strict_page_signatures is enabled."
        )
        raise TypeError(msg) from e
    except TypeError as e:
        msg = (
            f"Invalid type hints for page handler {qn!r}: {e}. "
            "Check Annotated metadata, string forward refs, and duplicate parameter names."
        )
        raise TypeError(msg) from e
    for name, param in sig.parameters.items():
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            msg = (
                f"Page handler {fn!r} must not use *args or **kwargs when "
                "strict_page_signatures is enabled."
            )
            raise TypeError(msg)
        if _has_depends_without_callable(param, hints, name):
            msg = f"Parameter {name!r} has Depends() without a callable dependency."
            raise TypeError(msg)
        if _depends_with_callable(param, hints, name):
            continue
        if _has_header_cookie(param, hints, name):
            continue
        if name in ("st", "client"):
            continue
        ann = hints.get(name, param.annotation)
        base = _strip_annotated(ann)
        if ann is inspect.Parameter.empty or base is Any:
            msg = (
                f"Unknown page parameter {name!r} without a recognized type annotation "
                "(strict_page_signatures). Annotate with an injectable type or Depends(...)."
            )
            raise TypeError(msg)
        if not _is_injectable_type(base):
            msg = (
                f"Unknown page parameter {name!r} with annotation {base!r} "
                "(strict_page_signatures). Use st, client, FluxLit, FluxlitSettings, "
                "FluxLitPublicUrls, ApiClient, SessionStore, FluxlitFeatureFlags, "
                "Depends(...), Header(...), or Cookie(...)."
            )
            raise TypeError(msg)


__all__ = ["validate_strict_page_signature"]
