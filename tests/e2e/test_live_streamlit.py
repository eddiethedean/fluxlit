"""Real browser checks: unified gateway proxies Streamlit including WebSocket."""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
def test_streamlit_loads_through_gateway(page: Page, fluxlit_live_url: str) -> None:
    page.goto(f"{fluxlit_live_url}/", wait_until="domcontentloaded")
    expect(page.get_by_text("FluxLit E2E", exact=False)).to_be_visible(timeout=90_000)
    expect(page.get_by_text("gateway_streamlit_ok", exact=True)).to_be_visible(timeout=90_000)


@pytest.mark.e2e
def test_api_docs_redirect_avoids_streamlit_trap(page: Page, fluxlit_live_url: str) -> None:
    page.goto(f"{fluxlit_live_url}/docs", wait_until="domcontentloaded")
    expect(page).to_have_url(re.compile(r".*/api/docs/?$"), timeout=30_000)
