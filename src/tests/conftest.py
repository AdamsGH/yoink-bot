"""Shared test fixtures."""
from __future__ import annotations

import pytest
import pytest_asyncio

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from yoink.storage.models import Base


@pytest_asyncio.fixture
async def session_factory(tmp_path):
    """In-memory SQLite database session factory for tests."""
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path}/test.db",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()
