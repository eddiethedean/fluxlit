from __future__ import annotations

import time
from pathlib import Path

from examples.session_stores.redis_store import RedisSessionStore
from examples.session_stores.sqlite_store import SQLiteSessionStore


class FakeRedis:
    def __init__(self) -> None:
        self.data: dict[str, tuple[str, float | None]] = {}

    def get(self, key: str) -> str | None:
        item = self.data.get(key)
        if item is None:
            return None
        value, expires_at = item
        if expires_at is not None and expires_at <= time.time():
            self.data.pop(key, None)
            return None
        return value

    def set(self, key: str, value: str) -> None:
        self.data[key] = (value, None)

    def setex(self, key: str, seconds: int, value: str) -> None:
        self.data[key] = (value, time.time() + seconds)

    def delete(self, key: str) -> None:
        self.data.pop(key, None)


def _exercise_store(store) -> None:
    assert store.get("sid") is None
    store.set("sid", {"count": 1, "name": "Ada"})
    assert store.get("sid") == {"count": 1, "name": "Ada"}
    store.set("sid", {"count": 2}, ttl_seconds=30)
    assert store.get("sid") == {"count": 2}
    store.delete("sid")
    assert store.get("sid") is None


def test_sqlite_session_store_contract(tmp_path: Path) -> None:
    _exercise_store(SQLiteSessionStore(tmp_path / "sessions.sqlite3"))


def test_sqlite_session_store_expires(tmp_path: Path) -> None:
    store = SQLiteSessionStore(tmp_path / "sessions.sqlite3")
    store.set("sid", {"count": 1}, ttl_seconds=-1)
    assert store.get("sid") is None


def test_redis_session_store_contract() -> None:
    _exercise_store(RedisSessionStore(FakeRedis()))
