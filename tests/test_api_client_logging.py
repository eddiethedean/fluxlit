"""Ensure ApiClient usage does not leak bearer material via stdlib/httpx log records."""

from __future__ import annotations

import logging

import httpx
import pytest

from fluxlit.client import ApiClient


def test_api_client_no_bearer_in_caplog_when_httpx_debug(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.delenv("FLUXLIT_INTERNAL_API_BASE", raising=False)
    secret = "UnitTest_Bearer_Token_Xy9DoNotLeak"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)

    caplog.set_level(logging.DEBUG)
    for name in ("httpx", "httpcore", "httpcore.http11"):
        caplog.set_level(logging.DEBUG, logger=name)

    with ApiClient(
        base_url="http://127.0.0.1:8000/api",
        auth_header_factory=lambda: {"Authorization": f"Bearer {secret}"},
    ) as client:
        client._client = httpx.Client(base_url=client._client.base_url, transport=transport)
        client.get("/z")

    joined = " ".join(f"{r.name}:{r.getMessage()}" for r in caplog.records)
    assert secret not in joined
