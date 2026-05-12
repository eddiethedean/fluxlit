"""Optional ``FLUXLIT_*`` feature flags for Streamlit pages (read-only)."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class FluxlitFeatureFlags:
    """Read-only flags derived from environment (no mutation after construction)."""

    experimental_yield_pages: bool

    @classmethod
    def from_environ(cls) -> FluxlitFeatureFlags:
        return cls(experimental_yield_pages=_truthy("FLUXLIT_EXPERIMENTAL_YIELD_PAGES"))


__all__ = ["FluxlitFeatureFlags"]
