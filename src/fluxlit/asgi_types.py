"""Shared ASGI-related type aliases (lifespan messages, scope, receive, send)."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any

from starlette.types import ASGIApp, Receive, Scope, Send

# Starlette uses ``Scope`` / ``Receive`` / ``Send`` for the outer shape; inner message dicts
# remain intentionally loose across ASGI versions and frameworks.
ASGIMessage = MutableMapping[str, Any]

__all__ = ["ASGIMessage", "ASGIApp", "Receive", "Scope", "Send"]
