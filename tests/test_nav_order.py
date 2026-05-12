"""Tests for :mod:`fluxlit.streamlit.nav_order`."""

from __future__ import annotations

from fluxlit.pages.navigation import NavigationModel
from fluxlit.pages.records import PageRecord
from fluxlit.streamlit.nav_order import navigation_sort_key


def test_navigation_sort_key_no_model() -> None:
    rec = PageRecord(path="/z", title="Z", fn=lambda st, client: None)
    assert navigation_sort_key(None, rec) == (0, "")


def test_navigation_sort_key_ordered() -> None:
    m = NavigationModel(order=("/b", "/"))
    ra = PageRecord(path="/", title="H", fn=lambda st, client: None)
    rb = PageRecord(path="/b", title="B", fn=lambda st, client: None)
    assert navigation_sort_key(m, rb)[0] < navigation_sort_key(m, ra)[0]


def test_navigation_sort_key_unknown_path() -> None:
    m = NavigationModel(order=("/a",))
    rx = PageRecord(path="/x", title="X", fn=lambda st, client: None)
    assert navigation_sort_key(m, rx)[0] == 2
