"""Lazy Prometheus metrics for the ASGI gateway."""

from __future__ import annotations

import importlib
import threading
from typing import Literal

from fluxlit.gateway._log import gateway_log
from fluxlit.gateway.contracts import GatewayPromCounter, GatewayPromHistogram

GATEWAY_PROMETHEUS_METRICS: tuple[dict[str, object], ...] = (
    {
        "name": "fluxlit_gateway_requests_total",
        "type": "counter",
        "labels": ("dispatch", "method_kind"),
        "stability": "stable",
    },
    {
        "name": "fluxlit_gateway_request_duration_seconds",
        "type": "histogram",
        "labels": ("dispatch",),
        "stability": "stable",
    },
)

_gateway_prom_cached: tuple[GatewayPromCounter, GatewayPromHistogram] | Literal[False] | None = None
_gateway_prom_lock = threading.Lock()


def get_gateway_prom_metrics() -> tuple[GatewayPromCounter, GatewayPromHistogram] | None:
    """Lazily construct Prometheus metrics (once per process) or None if unavailable."""
    global _gateway_prom_cached
    with _gateway_prom_lock:
        if _gateway_prom_cached is not None:
            if _gateway_prom_cached is False:
                return None
            return _gateway_prom_cached
        try:
            pc = importlib.import_module("prometheus_client")
            Counter = pc.Counter
            Histogram = pc.Histogram
            _gateway_prom_cached = (
                Counter(
                    "fluxlit_gateway_requests_total",
                    "Gateway requests observed at dispatch",
                    labelnames=("dispatch", "method_kind"),
                ),
                Histogram(
                    "fluxlit_gateway_request_duration_seconds",
                    "Wall time for one gateway request (dispatch wall clock)",
                    labelnames=("dispatch",),
                    buckets=(
                        0.001,
                        0.005,
                        0.01,
                        0.025,
                        0.05,
                        0.1,
                        0.25,
                        0.5,
                        1.0,
                        2.5,
                        5.0,
                        10.0,
                    ),
                ),
            )
        except ImportError:
            gateway_log.warning(
                "enable_gateway_prometheus_metrics is set but prometheus_client is not "
                "installed; install fluxlit[metrics] or prometheus-client"
            )
            _gateway_prom_cached = False
            return None
        return _gateway_prom_cached
