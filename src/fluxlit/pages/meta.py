"""Pydantic models for optional Streamlit page metadata (FluxLit 0.9)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PageMeta(BaseModel):
    """Optional metadata returned from a page handler or passed to :meth:`fluxlit.app.FluxLit.page`.

    Fields mirror :func:`streamlit.set_page_config` where applicable. Values returned **after**
    the handler runs cannot always update the browser title or layout (Streamlit only allows
    ``set_page_config`` as the first command); use :meth:`fluxlit.app.FluxLit.page` ``page_meta=``
    for static per-page config applied at the start of each run. Returned instances still
    drive sidebar breadcrumbs and the page manifest.
    """

    model_config = ConfigDict(extra="ignore")

    page_title: str | None = None
    page_icon: str | None = None
    layout: Literal["centered", "wide"] | None = None
    initial_sidebar_state: Literal["auto", "expanded", "collapsed"] | None = None
    breadcrumb: str | None = Field(
        default=None,
        description="If set, shown in the sidebar as a caption (post-run apply).",
    )
    order: int | None = Field(default=None, description="Optional sort hint for manifests / nav.")
    description: str | None = Field(
        default=None,
        description="Short description for manifests (not shown in Streamlit by default).",
    )
    children: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Optional nested nav/manifest entries (path + title keys).",
    )


# Public alias used in docs / annotations
Page = PageMeta

__all__ = ["Page", "PageMeta"]
