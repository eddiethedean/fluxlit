"""Declarative navigation ordering for multipage Streamlit apps."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NavigationModel:
    """Order registered pages by URL path (values not registered are ignored).

    Paths are compared after ``strip()``; ``\"/\"`` slugifies to ``\"home\"`` in the
    Streamlit entrypoint the same way as :func:`fluxlit.deep_links.match_nav_page`.
    """

    order: tuple[str, ...] = ()


__all__ = ["NavigationModel"]
