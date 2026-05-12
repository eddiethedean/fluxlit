"""JSON-serializable page manifest for docs, codegen, and link checkers."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import TYPE_CHECKING, Annotated, Any, get_args, get_origin, get_type_hints

from fluxlit.pages.di import Depends

if TYPE_CHECKING:
    from fluxlit.app import FluxLit


def _annotation_str(tp: Any) -> str:
    return str(tp)


def _depends_qualnames(fn: Callable[..., Any]) -> list[str]:
    sig = inspect.signature(fn)
    globalns = getattr(fn, "__globals__", None) or {}
    hints = get_type_hints(fn, globalns=globalns, include_extras=True)
    out: list[str] = []
    for name, param in sig.parameters.items():
        ann = hints.get(name, param.annotation)
        if get_origin(ann) is Annotated:
            for meta in get_args(ann)[1:]:
                if isinstance(meta, Depends) and meta.dependency is not None:
                    d = meta.dependency
                    mod = getattr(d, "__module__", "")
                    qn = getattr(d, "__qualname__", repr(d))
                    out.append(f"{mod}.{qn}" if mod else qn)
        if isinstance(param.default, Depends) and param.default.dependency is not None:
            d = param.default.dependency
            mod = getattr(d, "__module__", "")
            qn = getattr(d, "__qualname__", repr(d))
            s = f"{mod}.{qn}" if mod else qn
            if s not in out:
                out.append(s)
    return out


def build_page_manifest(app: FluxLit[Any], *, version: int = 1) -> dict[str, Any]:
    """Return a versioned manifest dict (``manifest_version`` **1** is experimental).

    Pages include path, title, tags, description, parameter metadata, and dependency
    qualnames (no code objects).
    """
    pages_out: list[dict[str, Any]] = []
    for rec in app.page_records:
        sig = inspect.signature(rec.fn)
        globalns = getattr(rec.fn, "__globals__", None) or {}
        hints = get_type_hints(rec.fn, globalns=globalns, include_extras=True)
        params: list[dict[str, str]] = []
        for pname, p in sig.parameters.items():
            ann = hints.get(pname, p.annotation)
            params.append({"name": pname, "annotation": _annotation_str(ann)})
        pages_out.append(
            {
                "path": rec.path,
                "title": rec.title,
                "tags": list(rec.tags),
                "description": rec.description,
                "icon": rec.icon,
                "parameters": params,
                "dependencies": _depends_qualnames(rec.fn),
            }
        )
    return {
        "manifest_version": version,
        "manifest_stability": "experimental",
        "title": app.settings.title,
        "pages": pages_out,
    }


__all__ = ["build_page_manifest"]
