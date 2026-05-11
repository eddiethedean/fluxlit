"""Shared pytest configuration for the ``tests/`` tree.

``pytest_plugins`` must live in this top-level conftest (not under ``tests/e2e/``)
per pytest 8+. Playwright stays optional: register only when ``pytest-playwright``
is installed (``pip install -e ".[e2e]"``).
"""

from __future__ import annotations

try:
    import pytest_playwright  # noqa: F401, PLC0415
except ImportError:
    pass
else:
    pytest_plugins = ["pytest_playwright"]
