"""Internal helpers for parsing environment variables."""

from __future__ import annotations

import os

_TRUTHY = frozenset({"1", "true", "yes", "on"})


def truthy_env(name: str) -> bool:
    """Return True when *name* is set to a common affirmative string (case-insensitive)."""
    return os.environ.get(name, "").strip().lower() in _TRUTHY
