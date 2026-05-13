"""Contract: ApiClient mirrors httpx typing via private modules.

``httpx`` does not expose all ``Client.request`` parameter types on the public package
surface; ``fluxlit.client`` imports from ``httpx._types`` and ``httpx._client``. This test
fails on import if those modules are reorganized—run the full suite after any httpx bump.
"""

from __future__ import annotations

import pytest

pytest.importorskip("httpx")

from httpx._client import UseClientDefault  # noqa: PLC2701
from httpx._types import (  # noqa: PLC2701
    AuthTypes,
    CookieTypes,
    HeaderTypes,
    QueryParamTypes,
    RequestContent,
    RequestData,
    RequestExtensions,
    RequestFiles,
    TimeoutTypes,
)

from fluxlit.client import ApiClient


def test_httpx_private_typing_modules_export_expected_names() -> None:
    assert UseClientDefault is not None
    assert ApiClient is not None
    for obj in (
        AuthTypes,
        CookieTypes,
        HeaderTypes,
        QueryParamTypes,
        RequestContent,
        RequestData,
        RequestExtensions,
        RequestFiles,
        TimeoutTypes,
    ):
        assert obj is not None
