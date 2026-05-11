"""Real browser checks: unified gateway proxies Streamlit including WebSocket."""

from __future__ import annotations

import re

import httpx
import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
def test_streamlit_loads_through_gateway(page: Page, fluxlit_live_url: str) -> None:
    page.goto(f"{fluxlit_live_url}/", wait_until="domcontentloaded")
    expect(page.get_by_text("FluxLit Smoke", exact=False)).to_be_visible(timeout=90_000)
    expect(page.get_by_text("fluxlit_smoke_ok", exact=True)).to_be_visible(timeout=90_000)


@pytest.mark.e2e
def test_api_docs_redirect_avoids_streamlit_trap(page: Page, fluxlit_live_url: str) -> None:
    page.goto(f"{fluxlit_live_url}/docs", wait_until="domcontentloaded")
    expect(page).to_have_url(re.compile(r".*/api/docs/?$"), timeout=30_000)


@pytest.mark.e2e
def test_subpath_streamlit_shell_and_api_health(
    page: Page,
    fluxlit_live_subpath_url: str,
) -> None:
    base = fluxlit_live_subpath_url
    page.goto(f"{base}/e2eapp/", wait_until="domcontentloaded")
    expect(page.get_by_text("FluxLit Smoke", exact=False)).to_be_visible(timeout=90_000)
    expect(page.get_by_text("fluxlit_smoke_ok", exact=True)).to_be_visible(timeout=90_000)
    r = httpx.get(f"{base}/e2eapp/api/healthz", timeout=10.0)
    assert r.status_code == 200
    assert r.json().get("status") == "ok"
