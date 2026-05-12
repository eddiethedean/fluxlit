"""Small in-process ring buffer of recent gateway dispatch decisions (debug mode)."""

from __future__ import annotations

from collections import deque

_ring: deque[tuple[str, str, str]] = deque(maxlen=32)


def record_gateway_dispatch(*, request_id: str, dispatch: str, path_in: str) -> None:
    _ring.append((request_id, dispatch, path_in))


def recent_gateway_dispatches() -> list[dict[str, str]]:
    return [{"request_id": rid, "dispatch": d, "path": p} for rid, d, p in _ring]
