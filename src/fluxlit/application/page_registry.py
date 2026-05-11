"""Streamlit page discovery and registration helpers."""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable
from types import FunctionType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fluxlit.app import FluxLit


def discover_streamlit_pages(app: FluxLit, directory: str, *, package: str) -> None:
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

    app._pages.sort(key=lambda t: (t[0], t[1]))


def register_streamlit_page(
    app: FluxLit, path: str, *, title: str | None = None
) -> Callable[[Callable[..., None]], Callable[..., None]]:
    """Implementation of :meth:`fluxlit.app.FluxLit.page` (decorator factory)."""

    def decorator(fn: Callable[..., None]) -> Callable[..., None]:
        default_title = "Page"
        if isinstance(fn, FunctionType):
            default_title = fn.__name__.replace("_", " ").title()
        app._pages.append((path, title or default_title, fn))
        return fn

    return decorator
