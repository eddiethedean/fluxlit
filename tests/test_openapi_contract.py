"""Contract test: default FluxLit OpenAPI shape (routes hidden from schema)."""

from __future__ import annotations

import json
from pathlib import Path

from fluxlit import FluxLit, FluxLitTestClient

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "openapi_contract_minimal.json"


def test_openapi_contract_minimal_app_matches_fixture() -> None:
    expected = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    fl = FluxLit(title="FluxLit OpenAPI Contract")
    live = FluxLitTestClient(fl).openapi()

    assert live.get("openapi") == expected["openapi"], (
        "OpenAPI version drift — update fixture if intentional (FastAPI/OpenAPI upgrade)."
    )
    assert live.get("paths") == expected["paths"], (
        "Default FluxLit API paths changed — update fixture or fix accidental route exposure."
    )
    assert live.get("servers") == expected["servers"], (
        "OpenAPI servers block changed — default API mount documentation may have shifted."
    )
