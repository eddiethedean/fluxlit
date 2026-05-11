"""Shared pytest configuration for the ``tests/`` tree.

``pytest_plugins`` must live in this top-level conftest (not under ``tests/e2e/``)
per pytest 8+. Playwright stays optional: register only when ``pytest-playwright``
is installed (``pip install -e ".[e2e]"``).
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from fluxlit.config import FluxlitSettings

try:
    import pytest_playwright  # noqa: F401, PLC0415
except ImportError:
    pass
else:
    pytest_plugins = ["pytest_playwright"]


@pytest.fixture
def requires_streamlit_apptest() -> None:
    """Skip when Streamlit is too old for ``streamlit.testing.v1.AppTest``."""
    streamlit = pytest.importorskip("streamlit")
    major, minor = (int(x) for x in streamlit.__version__.split(".")[:2])
    if (major, minor) < (1, 30):
        pytest.skip("Streamlit AppTest requires 1.30+")


@pytest.fixture
def gateway_test_client_factory():
    """Factory: ``build_gateway`` wrapped in :class:`starlette.testclient.TestClient`."""

    def _factory(
        *,
        api_app: FastAPI | None = None,
        upstream: str = "http://127.0.0.1:9",
        api_prefix: str = "/api",
        root_mount: str = "",
        access_log: bool = False,
        upstream_resolver: Callable[[], str] | None = None,
        proxy_settings: FluxlitSettings | None = None,
    ) -> TestClient:
        from fluxlit.gateway import build_gateway

        inner = api_app if api_app is not None else FastAPI()
        if upstream_resolver is not None:
            gw = build_gateway(
                inner,
                upstream,
                upstream_resolver=upstream_resolver,
                api_prefix=api_prefix,
                root_mount=root_mount,
                access_log=access_log,
                proxy_settings=proxy_settings,
            )
        else:
            gw = build_gateway(
                inner,
                upstream,
                api_prefix=api_prefix,
                root_mount=root_mount,
                access_log=access_log,
                proxy_settings=proxy_settings,
            )
        return TestClient(gw)

    return _factory
