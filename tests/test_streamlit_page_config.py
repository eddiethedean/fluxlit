"""Unit tests for :mod:`fluxlit.streamlit_page_config` (no Streamlit import required)."""

from __future__ import annotations

import pytest

from fluxlit.streamlit_page_config import build_set_page_config_kwargs


def test_build_page_config_defaults_title_only() -> None:
    out = build_set_page_config_kwargs(settings_title="App", streamlit_page_config={})
    assert out == {"page_title": "App"}


def test_build_page_config_explicit_page_title() -> None:
    out = build_set_page_config_kwargs(
        settings_title="Default",
        streamlit_page_config={"page_title": "Override"},
    )
    assert out == {"page_title": "Override"}


def test_build_page_config_empty_page_title_falls_back_to_settings() -> None:
    out = build_set_page_config_kwargs(
        settings_title="Fallback",
        streamlit_page_config={"page_title": ""},
    )
    assert out == {"page_title": "Fallback"}


@pytest.mark.parametrize(
    ("raw", "expected_extra"),
    [
        ({"layout": "wide"}, {"layout": "wide"}),
        ({"page_icon": "🚀"}, {"page_icon": "🚀"}),
        ({"initial_sidebar_state": "collapsed"}, {"initial_sidebar_state": "collapsed"}),
        (
            {"menu_items": {"about": "https://example.com/about"}},
            {"menu_items": {"about": "https://example.com/about"}},
        ),
    ],
)
def test_build_page_config_supported_keys(
    raw: dict[str, object], expected_extra: dict[str, object]
) -> None:
    out = build_set_page_config_kwargs(settings_title="T", streamlit_page_config=raw)
    assert out["page_title"] == "T"
    for k, v in expected_extra.items():
        assert out[k] == v


def test_build_page_config_skips_none_and_empty_string() -> None:
    out = build_set_page_config_kwargs(
        settings_title="T",
        streamlit_page_config={
            "layout": None,
            "page_icon": "",
            "initial_sidebar_state": "expanded",
        },
    )
    assert out == {"page_title": "T", "initial_sidebar_state": "expanded"}


def test_build_page_config_ignores_unknown_keys() -> None:
    out = build_set_page_config_kwargs(
        settings_title="T",
        streamlit_page_config={"not_a_streamlit_key": "x", "layout": "wide"},
    )
    assert "not_a_streamlit_key" not in out
    assert out == {"page_title": "T", "layout": "wide"}


def test_build_page_config_does_not_mutate_input_mapping() -> None:
    cfg = {"page_title": "X", "layout": "wide"}
    build_set_page_config_kwargs(settings_title="T", streamlit_page_config=cfg)
    assert cfg == {"page_title": "X", "layout": "wide"}
