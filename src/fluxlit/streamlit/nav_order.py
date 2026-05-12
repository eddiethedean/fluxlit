"""Multipage navigation ordering (used by the Streamlit entrypoint)."""

from __future__ import annotations

from fluxlit.pages.navigation import NavigationModel
from fluxlit.pages.records import PageRecord


def navigation_sort_key(model: NavigationModel | None, rec: PageRecord) -> tuple[int, str]:
    """Sort key: lower index first when *model* defines ``order``; stable otherwise."""
    slug = rec.path.strip("/") or "home"
    if model is None or not model.order:
        return (0, "")
    keys = [p.strip("/") or "home" for p in model.order]
    try:
        return (keys.index(slug), slug)
    except ValueError:
        return (len(keys) + 1, slug)


__all__ = ["navigation_sort_key"]
