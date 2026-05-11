"""SQLite-backed URL session store example.

This example uses only the Python standard library. It is suitable for local demos
and single-host deployments where a shared SQLite file is acceptable.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from fluxlit.config import JsonValue
from fluxlit.url_session import SessionStore


class SQLiteSessionStore(SessionStore):
    """A small `SessionStore` implementation backed by SQLite."""

    def __init__(self, path: str | Path = "fluxlit-sessions.sqlite3") -> None:
        self.path = Path(path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS fluxlit_sessions (
                    session_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    expires_at REAL
                )
                """
            )

    def get(self, session_id: str) -> dict[str, JsonValue] | None:
        now = time.time()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload, expires_at FROM fluxlit_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if row is None:
                return None
            payload, expires_at = row
            if expires_at is not None and float(expires_at) <= now:
                conn.execute("DELETE FROM fluxlit_sessions WHERE session_id = ?", (session_id,))
                return None
        return json.loads(str(payload))

    def set(
        self,
        session_id: str,
        data: dict[str, JsonValue],
        *,
        ttl_seconds: float | None = None,
    ) -> None:
        expires_at = None if ttl_seconds is None else time.time() + float(ttl_seconds)
        payload = json.dumps(data, separators=(",", ":"), sort_keys=True)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO fluxlit_sessions(session_id, payload, expires_at)
                VALUES (?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    payload = excluded.payload,
                    expires_at = excluded.expires_at
                """,
                (session_id, payload, expires_at),
            )

    def delete(self, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM fluxlit_sessions WHERE session_id = ?", (session_id,))
