"""Protocol contracts for optional gateway metrics (Prometheus)."""

from __future__ import annotations

from typing import Protocol


class GatewayPromCounterLabels(Protocol):
    def inc(self) -> None: ...


class GatewayPromCounter(Protocol):
    def labels(self, *, dispatch: str, method_kind: str) -> GatewayPromCounterLabels: ...


class GatewayPromHistogramLabels(Protocol):
    def observe(self, value: float) -> None: ...


class GatewayPromHistogram(Protocol):
    def labels(self, *, dispatch: str) -> GatewayPromHistogramLabels: ...
