"""
Pytest configuration and fixtures for the fact_inventory test suite.
"""

import asyncio
from collections.abc import AsyncGenerator

import pytest
from app.app_factory import create_app
from litestar import Litestar
from litestar.testing import AsyncTestClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


@pytest.fixture(scope="session")
def event_loop_policy():
    """Set the event loop policy for the session."""

    return asyncio.get_event_loop_policy()


@pytest.fixture(scope="session")
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create a session-scoped test database engine."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
async def sessionmaker_fixture(
    test_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Create a sessionmaker for session-scoped test database sessions."""
    return async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest.fixture
async def db_session(
    sessionmaker_fixture: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session for a test, with automatic rollback."""
    async with sessionmaker_fixture() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def app(
    db_session: AsyncSession,  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,
) -> Litestar:
    """Create a Litestar app instance with mocked database."""
    monkeypatch.setenv("DATABASE_URI", "sqlite+aiosqlite:///:memory:")
    return create_app()


@pytest.fixture
async def client(app: Litestar) -> AsyncGenerator[AsyncTestClient, None]:
    """Provide an async test client for making requests."""
    async with AsyncTestClient(app=app) as client:
        yield client
