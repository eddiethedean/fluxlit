"""Contract tests for stability-chartered metrics and manifests."""

from __future__ import annotations

from typing import Any

import pytest

from fluxlit import FluxLit
from fluxlit.gateway.metrics import GATEWAY_PROMETHEUS_METRICS, get_gateway_prom_metrics
from fluxlit.pages.manifest import (
    MANIFEST_V1_PAGE_ALLOWED_KEYS,
    MANIFEST_V1_ROOT_KEYS,
    build_page_manifest,
)


def test_gateway_prometheus_names_match_charter() -> None:
    pair = get_gateway_prom_metrics()
    assert pair is not None
    counter, histogram = pair
    counter_series = {s.name for s in counter.collect()}
    histogram_series = {s.name for s in histogram.collect()}
    histogram_charter = next(
        m["name"] for m in GATEWAY_PROMETHEUS_METRICS if m["type"] == "histogram"
    )
    counter_charter = next(m["name"] for m in GATEWAY_PROMETHEUS_METRICS if m["type"] == "counter")
    assert histogram_series == {histogram_charter}
    assert counter_charter.endswith("_total")
    assert counter_charter.removesuffix("_total") in counter_series
    assert len(counter_series) == 1 and len(histogram_series) == 1


def test_manifest_v1_keys_match_charter() -> None:
    app = FluxLit(title="Charter")

    @app.page("/", title="Home")
    def _home(st: Any) -> None:
        st.write("ok")

    manifest = build_page_manifest(app)
    assert set(manifest) == MANIFEST_V1_ROOT_KEYS
    assert len(manifest["pages"]) == 1
    page_keys = set(manifest["pages"][0])
    assert page_keys <= MANIFEST_V1_PAGE_ALLOWED_KEYS


@pytest.mark.parametrize(
    "label_tuple",
    [m["labels"] for m in GATEWAY_PROMETHEUS_METRICS],
)
def test_gateway_prometheus_label_names_are_tuples_of_strings(
    label_tuple: tuple[str, ...],
) -> None:
    assert isinstance(label_tuple, tuple)
    assert all(isinstance(x, str) for x in label_tuple)
