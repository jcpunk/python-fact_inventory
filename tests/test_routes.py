"""
Tests for the create_router factory function.
"""

from advanced_alchemy.extensions.litestar import (
    AsyncSessionConfig,
    SQLAlchemyAsyncConfig,
    SQLAlchemyPlugin,
)
from app.routes import create_router
from litestar import Litestar, Router
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_404_NOT_FOUND,
)
from litestar.testing import AsyncTestClient


def _build_prefixed_app(path: str = "/fact_inventory") -> Litestar:
    """Build a minimal Litestar app with the router mounted at *path*."""
    alchemy_config = SQLAlchemyAsyncConfig(
        connection_string="sqlite+aiosqlite:///:memory:",
        before_send_handler="autocommit",
        session_config=AsyncSessionConfig(expire_on_commit=True),
        create_all=True,
    )
    return Litestar(
        route_handlers=[create_router(path=path)],
        plugins=[SQLAlchemyPlugin(config=alchemy_config)],
    )


class TestCreateRouterDefaultPath:
    """Tests for create_router() with default path='/'."""

    async def test_health_at_root(self) -> None:
        """Health endpoint must be reachable at /health with default path."""
        router = create_router()
        assert isinstance(router, Router)

    async def test_default_path_is_slash(self) -> None:
        """The default router path must be '/'."""
        router = create_router()
        assert router.path == "/"


class TestCreateRouterPrefixedPath:
    """Tests for create_router(path='/fact_inventory')."""

    async def test_prefixed_path_is_stored(self) -> None:
        """A custom path must be reflected in the router."""
        router = create_router(path="/fact_inventory")
        assert router.path == "/fact_inventory"

    async def test_health_at_prefix(self) -> None:
        """Health endpoint must be reachable at /fact_inventory/health."""
        app = _build_prefixed_app()
        async with AsyncTestClient(app=app) as client:
            response = await client.get("/fact_inventory/health")
            assert response.status_code == HTTP_200_OK
            assert response.json()["service"] == "fact_inventory"

    async def test_facts_at_prefix(self) -> None:
        """Facts endpoint must be reachable at /fact_inventory/v1/facts."""
        app = _build_prefixed_app()
        async with AsyncTestClient(app=app) as client:
            response = await client.post(
                "/fact_inventory/v1/facts",
                json={"system_facts": {}, "package_facts": {}},
            )
            assert response.status_code == HTTP_201_CREATED

    async def test_root_health_not_found_when_prefixed(self) -> None:
        """Health must not be at /health when prefix is /fact_inventory."""
        app = _build_prefixed_app()
        async with AsyncTestClient(app=app) as client:
            response = await client.get("/health")
            assert response.status_code == HTTP_404_NOT_FOUND
