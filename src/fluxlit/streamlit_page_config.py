"""Pure helpers for Streamlit ``set_page_config`` (testable without importing Streamlit UI)."""

from __future__ import annotations

from typing import Any


def build_set_page_config_kwargs(
    *,
    settings_title: str,
    streamlit_page_config: dict[str, Any],
) -> dict[str, Any]:
    """Build kwargs for :func:`streamlit.set_page_config` from settings.

    Merges ``page_title`` from the mapping when present; otherwise uses *settings_title*.
    Includes only supported Streamlit keys with non-empty values; other keys in the
    mapping are ignored.
    """
    raw = dict(streamlit_page_config)
    page_title = raw.pop("page_title", None) or settings_title
    kwargs: dict[str, Any] = {"page_title": page_title}
    for key in ("page_icon", "layout", "initial_sidebar_state", "menu_items"):
        if key not in raw:
            continue
        val = raw[key]
        if val is None or val == "":
            continue
        kwargs[key] = val
    return kwargs
