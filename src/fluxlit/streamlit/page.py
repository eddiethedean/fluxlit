"""Typing helpers for Streamlit page callables."""

from __future__ import annotations

from typing import Any, Protocol

from fluxlit.client import ApiClient
from fluxlit.pages.meta import PageMeta


class PageFn(Protocol):
    """Protocol for functions registered with :meth:`fluxlit.app.FluxLit.page`.

    Streamlit passes the ``streamlit`` module as ``st`` and an :class:`~fluxlit.client.ApiClient`
    bound to the internal API base. Handlers may return :class:`~fluxlit.pages.meta.PageMeta`
    for post-run metadata (breadcrumbs, etc.).
    """

    def __call__(self, st: Any, client: ApiClient, /) -> PageMeta | None:
        """Render the page; may use ``st`` widgets and ``client`` for HTTP calls."""
        ...


__all__ = ["PageFn"]
