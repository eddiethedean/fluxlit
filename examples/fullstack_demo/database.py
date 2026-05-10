"""Async SQLite (rapsqlite) engine and session factory; sync URL for Alembic."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Single-file DB next to this package; override with DATABASE_URL if needed (sync sqlite: form).
_DEFAULT_SQLITE = os.path.join(os.path.dirname(__file__), "fullstack_demo.db")
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{_DEFAULT_SQLITE}")

if not DATABASE_URL.startswith("sqlite:"):
    msg = "DATABASE_URL must be a sqlite: URL (Alembic uses sync sqlite3 on the same file)."
    raise ValueError(msg)

ASYNC_DATABASE_URL = DATABASE_URL.replace("sqlite:", "sqlite+rapsqlite:", 1)

engine = create_async_engine(ASYNC_DATABASE_URL)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
