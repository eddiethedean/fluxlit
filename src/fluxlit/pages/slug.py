"""Stable ``url_path`` slug for multipage Streamlit (matches gateway entrypoint)."""


def page_slug(path: str) -> str:
    """Sidebar ``url_path`` segment (matches Streamlit entrypoint)."""
    return path.strip("/") or "home"


__all__ = ["page_slug"]
