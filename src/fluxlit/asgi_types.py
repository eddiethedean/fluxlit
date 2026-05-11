"""Shared ASGI-related type aliases (lifespan messages, dynamic scope fields)."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any

# Starlette uses ``Scope`` / ``Receive`` / ``Send`` for the outer shape; inner message dicts
# remain intentionally loose across ASGI versions and frameworks.
ASGIMessage = MutableMapping[str, Any]
