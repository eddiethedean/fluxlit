"""Redis-backed URL session store example.

The class accepts a Redis-like client to avoid making Redis a FluxLit dependency.
Clients such as `redis.Redis` expose the `get`, `set`, `setex`, and `delete`
methods used here.
"""

from __future__ import annotations

import json
from typing import Any

from fluxlit.config import JsonValue
from fluxlit.url_session import SessionStore


class RedisSessionStore(SessionStore):
    """A `SessionStore` implementation for Redis-compatible clients."""

    def __init__(self, redis_client: Any, *, prefix: str = "fluxlit:sid:") -> None:
        self.redis = redis_client
        self.prefix = prefix

    def _key(self, session_id: str) -> str:
        return f"{self.prefix}{session_id}"

    def get(self, session_id: str) -> dict[str, JsonValue] | None:
        raw = self.redis.get(self._key(session_id))
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(str(raw))

    def set(
        self,
        session_id: str,
        data: dict[str, JsonValue],
        *,
        ttl_seconds: float | None = None,
    ) -> None:
        payload = json.dumps(data, separators=(",", ":"), sort_keys=True)
        if ttl_seconds is None:
            self.redis.set(self._key(session_id), payload)
        else:
            self.redis.setex(self._key(session_id), int(ttl_seconds), payload)

    def delete(self, session_id: str) -> None:
        self.redis.delete(self._key(session_id))
