"""Pytest fixtures: isolated DB, ``get_db`` override, :class:`fluxlit.testing.FluxLitTestClient`."""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from fluxlit.testing import FluxLitTestClient

EXAMPLE_ROOT = Path(__file__).resolve().parent.parent

os.environ.setdefault("DATABASE_URL", f"sqlite:///{EXAMPLE_ROOT / '.pytest_import.db'}")

if str(EXAMPLE_ROOT) not in sys.path:
    sys.path.insert(0, str(EXAMPLE_ROOT))

import main as demo_main  # noqa: E402
from database import get_db  # noqa: E402


@pytest.fixture
def async_engine(tmp_path: Path):
    """Per-test rapsqlite file DB; sync wrapper around async engine lifecycle."""
    db_path = tmp_path / "test.db"
    url = f"sqlite+rapsqlite:///{db_path}"
    engine = create_async_engine(url)

    async def setup() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    asyncio.run(setup())
    try:
        yield engine
    finally:

        async def teardown() -> None:
            await engine.dispose()

        asyncio.run(teardown())


@pytest.fixture
def fluxlit_client(async_engine):
    """Production-like routing: requests go through the gateway with ``/api`` prefix."""
    session_factory = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    demo_main.app.api.dependency_overrides[get_db] = _override_db
    try:
        yield FluxLitTestClient(demo_main.app)
    finally:
        demo_main.app.api.dependency_overrides.clear()
