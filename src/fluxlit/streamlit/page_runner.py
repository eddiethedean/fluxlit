"""Invoke a registered Streamlit page (testable without loading ``streamlit.main``)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fluxlit.client import ApiClient
from fluxlit.pages.di import resolve_and_call_page
from fluxlit.pages.records import PageRecord


def run_page_record(
    rec: PageRecord,
    st: Any,
    client: ApiClient,
    app: Any,
    overrides: Mapping[str, Any] | None = None,
) -> Any:
    """Run *rec* through dependency resolution and the user handler."""
    return resolve_and_call_page(rec, st, client, app, overrides)


__all__ = ["run_page_record"]
