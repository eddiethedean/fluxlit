"""Streamlit smoke test using :meth:`fluxlit.testing.FluxLitTestClient.streamlit` (``AppTest``)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fluxlit.testing import FluxLitTestClient

_EXAMPLE_ROOT = Path(__file__).resolve().parent.parent


def test_streamlit_home_renders_without_error(fluxlit_client: FluxLitTestClient) -> None:
    streamlit = pytest.importorskip("streamlit")
    if tuple(int(x) for x in streamlit.__version__.split(".")[:2]) < (1, 30):
        pytest.skip("Streamlit AppTest requires 1.30+")

    at = fluxlit_client.streamlit(target="app:app", extra_sys_path=_EXAMPLE_ROOT)
    assert len(at.exception) == 0
    markdown_values = [getattr(m, "value", None) or "" for m in at.markdown]
    assert any("FluxLit demo" in str(v) for v in markdown_values)
