"""Tests for :mod:`fluxlit.streamlit.nav_build`."""

from __future__ import annotations

import warnings
from types import SimpleNamespace

import pytest

from fluxlit.pages.meta import PageMeta
from fluxlit.pages.records import PageRecord
from fluxlit.streamlit.nav_build import (
    apply_children_overrides,
    order_records_with_children,
    page_slug,
)


def test_page_slug() -> None:
    assert page_slug("/") == "home"
    assert page_slug("/reports") == "reports"


def test_order_empty_records() -> None:
    assert order_records_with_children([]) == []


def test_order_records_topo_moves_child_after_parent() -> None:
    def _a(st, client):
        del st, client

    def _z(st, client):
        del st, client

    z = PageRecord(
        path="/z",
        title="Z",
        fn=_z,
        page_meta=PageMeta(children=[{"path": "/a"}]),
    )
    a = PageRecord(path="/a", title="A", fn=_a)
    out = order_records_with_children([a, z])
    assert [r.path for r in out] == ["/z", "/a"]


def test_order_records_with_children_unknown_warns() -> None:
    def _a(st, client):
        del st, client

    home = PageRecord(
        path="/",
        title="Home",
        fn=_a,
        page_meta=PageMeta(children=[{"path": "/missing"}]),
    )
    with pytest.warns(UserWarning, match="unknown path"):
        order_records_with_children([home])


def test_apply_children_overrides_title() -> None:
    def _a(st, client):
        del st, client

    home = PageRecord(
        path="/",
        title="Home",
        fn=_a,
        page_meta=PageMeta(
            children=[{"path": "/", "title": "Welcome", "icon": "🧪"}],
        ),
    )
    out = apply_children_overrides([home])
    assert out[0].title == "Welcome"
    assert out[0].icon == "🧪"


def test_apply_children_overrides_no_warnings_on_empty() -> None:
    def _a(st, client):
        del st, client

    rec = PageRecord(path="/", title="Home", fn=_a)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert apply_children_overrides([rec]) == [rec]


def test_order_without_children_preserves_registration_order() -> None:
    def _a(st, client):
        del st, client

    def _b(st, client):
        del st, client

    a = PageRecord(path="/a", title="A", fn=_a)
    b = PageRecord(path="/b", title="B", fn=_b)
    assert order_records_with_children([a, b]) == [a, b]


def test_apply_children_skips_non_dict_and_missing_path() -> None:
    def _f(st, client):
        del st, client

    meta = SimpleNamespace(children=["x", {}, {"path": None}])
    r = PageRecord(path="/", title="H", fn=_f, page_meta=meta)  # type: ignore[arg-type]
    assert apply_children_overrides([r]) == [r]


def test_apply_children_title_only_uses_replace() -> None:
    def _f(st, client):
        del st, client

    r = PageRecord(
        path="/",
        title="H",
        fn=_f,
        page_meta=PageMeta(children=[{"path": "/", "title": "N"}]),
    )
    out = apply_children_overrides([r])
    assert out[0].title == "N"
    assert out[0].icon is None


def test_apply_children_override_same_as_record_keeps_identity() -> None:
    def _f(st, client):
        del st, client

    r = PageRecord(
        path="/",
        title="H",
        fn=_f,
        page_meta=PageMeta(children=[{"path": "/", "title": "H"}]),
    )
    out = apply_children_overrides([r])
    assert out[0] is r


def test_order_skips_non_dict_and_empty_child() -> None:
    def _h(st, client):
        del st, client

    meta = SimpleNamespace(children=["bad", {}])
    r = PageRecord(path="/", title="H", fn=_h, page_meta=meta)  # type: ignore[arg-type]
    assert order_records_with_children([r]) == [r]


def test_order_skips_self_referential_child() -> None:
    def _h(st, client):
        del st, client

    r = PageRecord(
        path="/",
        title="H",
        fn=_h,
        page_meta=PageMeta(children=[{"path": "/"}]),
    )
    assert order_records_with_children([r]) == [r]


def test_order_cycle_still_lists_all_pages() -> None:
    def _a(st, client):
        del st, client

    def _z(st, client):
        del st, client

    a = PageRecord(
        path="/a",
        title="A",
        fn=_a,
        page_meta=PageMeta(children=[{"path": "/z"}]),
    )
    z = PageRecord(
        path="/z",
        title="Z",
        fn=_z,
        page_meta=PageMeta(children=[{"path": "/a"}]),
    )
    with pytest.warns(UserWarning, match="cycle"):
        out = order_records_with_children([a, z])
    assert {rec.path for rec in out} == {"/a", "/z"}
