"""Streamlit page metadata, DI markers, query/session helpers, and manifests (FluxLit 0.9+)."""

from __future__ import annotations

from typing import Any

from fluxlit.pages.di import Cookie, Depends, Header, resolve_page_kwargs
from fluxlit.pages.manifest import build_page_manifest
from fluxlit.pages.meta import Page, PageMeta
from fluxlit.pages.navigation import NavigationModel
from fluxlit.pages.query import Query, parse_query_params, parse_query_params_adapter
from fluxlit.pages.records import PageRecord
from fluxlit.pages.session_state import SessionModel
from fluxlit.pages.slug import page_slug

__all__ = [
    "Cookie",
    "Depends",
    "Header",
    "NavigationModel",
    "Page",
    "PageMeta",
    "PageRecord",
    "Query",
    "SessionModel",
    "build_page_manifest",
    "page_slug",
    "parse_query_params",
    "parse_query_params_adapter",
    "resolve_page_kwargs",
    "validate_fluxlit_pages",
]


def __getattr__(name: str) -> Any:
    if name == "validate_fluxlit_pages":
        from fluxlit.pages.validate import validate_fluxlit_pages

        return validate_fluxlit_pages
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
