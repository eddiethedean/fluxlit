"""Internal registration record for Streamlit pages."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from fluxlit.pages.meta import PageMeta


@dataclass
class PageRecord:
    """Registered Streamlit page (path, title, handler, and optional static metadata)."""

    path: str
    title: str
    fn: Callable[..., Any]
    tags: tuple[str, ...] = field(default_factory=tuple)
    description: str = ""
    icon: str | None = None
    page_meta: PageMeta | None = None


__all__ = ["PageRecord"]
