"""Typing helpers for Streamlit page callables."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from fluxlit.client import ApiClient


class PageFn(Protocol):
    """Protocol for functions registered with :meth:`fluxlit.app.FluxLit.page`.

    Streamlit passes the ``streamlit`` module as ``st`` and an :class:`~fluxlit.client.ApiClient`
    bound to the internal API base.
    """

    def __call__(self, st: Any, client: ApiClient, /) -> None:
        """Render the page; may use ``st`` widgets and ``client`` for HTTP calls."""
        ...
