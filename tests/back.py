"""
Pytest base configuration fixtures for the fact_inventory test suite.
"""

import asyncio
from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest
from app.app_factory import create_app
from app.fact_inventory.schemas import HostFacts
from litestar import Litestar
from litestar.testing import AsyncTestClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create a test database engine using SQLite in-memory."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(HostFacts.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture(scope="session")
async def sessionmaker_fixture(
    test_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Create a sessionmaker for test database sessions."""
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
    """Create a test Litestar application with mocked database."""
    # Set test environment variables
    monkeypatch.setenv("DATABASE_URI", "sqlite+aiosqlite:///:memory:")

    return create_app()


@pytest.fixture
async def client(app: Litestar) -> AsyncGenerator[AsyncTestClient, None]:
    """Provide an async test client for making requests."""
    async with AsyncTestClient(app=app) as client:
        yield client


@pytest.fixture
def sample_facts() -> dict[str, Any]:
    """Provide sample fact data for testing."""
    return {
        "system_facts": {
            "os": "RHEL",
            "version": "9.2",
            "hostname": "test-server-01",
            "architecture": "x86_64",
            "kernel": "5.14.0-284.11.1.el9_2.x86_64",
        },
        "package_facts": {
            "installed": ["vim", "git", "htop", "nginx"],
            "total_packages": 1523,
        },
    }


@pytest.fixture
def minimal_facts() -> dict[str, Any]:
    """Provide minimal fact data for testing."""
    return {
        "system_facts": {},
        "package_facts": {},
    }


@pytest.fixture
def large_facts() -> dict[str, Any]:
    """Provide large fact data near the size limit."""
    return {
        "system_facts": {f"key_{i}": f"value_{i}" * 100 for i in range(1000)},
        "package_facts": {
            "installed": [f"package-{i}" for i in range(5000)],
        },
    }
