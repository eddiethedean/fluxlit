"""Streamlit page discovery and registration helpers."""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from collections.abc import Callable, Sequence
from types import FunctionType
from typing import TYPE_CHECKING, Annotated, Any, TypeAlias, get_args, get_origin, get_type_hints

from fluxlit.pages.meta import PageMeta
from fluxlit.pages.records import PageRecord
from fluxlit.pages.signature import validate_strict_page_signature
from fluxlit.pages.slug import page_slug
from fluxlit.url_session import SessionStore

if TYPE_CHECKING:
    from fluxlit.app import FluxLit

    FluxLitApp: TypeAlias = FluxLit[Any]


def _docstring_first_line(fn: Callable[..., Any]) -> str:
    doc = getattr(fn, "__doc__", None)
    if not doc or not str(doc).strip():
        return ""
    return str(doc).strip().split("\n", maxsplit=1)[0].strip()


def discover_streamlit_pages(app: FluxLitApp, directory: str, *, package: str) -> None:
    """Implementation of :meth:`fluxlit.app.FluxLit.discover_pages` (mutates *app*)."""
    parent = importlib.import_module(package)
    paths = getattr(parent, "__path__", None)
    if paths is None:
        msg = f"{package!r} must be a package to discover pages"
        raise TypeError(msg)
    subpkg = f"{package}.{directory}"
    try:
        importlib.import_module(subpkg)
    except ImportError as e:
        msg = f"Cannot import page package {subpkg!r}: {e}"
        raise ImportError(msg) from e

    pkg = importlib.import_module(subpkg)
    for modinfo in sorted(
        pkgutil.iter_modules(pkg.__path__, f"{subpkg}."),
        key=lambda m: m.name,
    ):
        if modinfo.ispkg or modinfo.name.rpartition(".")[-1].startswith("_"):
            continue
        mod = importlib.import_module(modinfo.name)
        register = getattr(mod, "register", None)
        if register is None:
            continue
        register(app)

    app._pages.sort(key=lambda r: (r.path, r.title))


def _strip_annotated(ann: Any) -> Any:
    if get_origin(ann) is Annotated:
        return get_args(ann)[0]
    return ann


def _validate_session_store_on_page(app: FluxLitApp, fn: Callable[..., Any]) -> None:
    if app.session_store is not None:
        return
    sig = inspect.signature(fn)
    try:
        hints = get_type_hints(fn, globalns=getattr(fn, "__globals__", None) or {})
    except (NameError, TypeError):
        return
    for name, param in sig.parameters.items():
        if name in ("st", "client"):
            continue
        if param.default is not inspect.Parameter.empty:
            continue
        base = _strip_annotated(hints.get(name, param.annotation))
        if base is SessionStore:
            msg = (
                f"Page handler {getattr(fn, '__qualname__', repr(fn))!r} requires "
                "SessionStore injection but FluxLit(session_store=None). Pass "
                "session_store= to FluxLit(...) or remove the SessionStore parameter."
            )
            raise ValueError(msg)


def register_streamlit_page(
    app: FluxLitApp,
    path: str,
    *,
    title: str | None = None,
    icon: str | None = None,
    tags: Sequence[str] | None = None,
    page_meta: PageMeta | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Implementation of :meth:`fluxlit.app.FluxLit.page` (decorator factory)."""

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        if app.settings.strict_page_signatures:
            validate_strict_page_signature(fn)
        _validate_session_store_on_page(app, fn)
        default_title = "Page"
        if isinstance(fn, FunctionType):
            default_title = fn.__name__.replace("_", " ").title()
        if any(r.path == path for r in app._pages):
            msg = f"Duplicate Streamlit page path {path!r} is already registered"
            raise ValueError(msg)
        slug = page_slug(path)
        for r in app._pages:
            if page_slug(r.path) == slug:
                msg = (
                    f"Streamlit page url_path slug {slug!r} is already used by path "
                    f"{r.path!r}; registering {path!r} would collide (same sidebar segment)"
                )
                raise ValueError(msg)
        desc = _docstring_first_line(fn)
        tag_tuple = tuple(tags or ())
        rec = PageRecord(
            path=path,
            title=title or default_title,
            fn=fn,
            tags=tag_tuple,
            description=desc,
            icon=icon,
            page_meta=page_meta,
        )
        app._pages.append(rec)
        return fn

    return decorator


__all__ = ["discover_streamlit_pages", "register_streamlit_page"]
