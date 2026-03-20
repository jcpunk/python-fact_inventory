"""
fact_inventory — ASGI sub-application for collecting and storing system facts.

This package is intentionally independent of any specific application factory.
The only public API integrators need is the ``routes`` list::

    from litestar import Litestar
    from advanced_alchemy.extensions.litestar import (
        SQLAlchemyPlugin,
        SQLAlchemyAsyncConfig,
    )
    from app.fact_inventory.routes import routes

    app = Litestar(
        route_handlers=[*routes],
        plugins=[SQLAlchemyPlugin(config=SQLAlchemyAsyncConfig(...))],
    )

Required host-application configuration
----------------------------------------
``SQLAlchemyPlugin``
    An ``advanced_alchemy`` SQLAlchemy plugin **must** be registered on the
    Litestar application.  The plugin provides an ``AsyncSession`` through
    Litestar's dependency-injection system, which fact_inventory injects into
    its handlers automatically.

Optional Litestar dependency
----------------------------
``rate_limit_minutes`` (``int``, default ``27``)
    Minimum minutes that must elapse between successive fact submissions from
    the same client IP address.  fact_inventory declares this as a
    ``Dependency(default=27)`` on its handler, so it works out of the box.
    To override, register a ``Provide`` at the application level::

        from litestar.di import Provide

        app = Litestar(
            route_handlers=[*routes],
            dependencies={
                "rate_limit_minutes": Provide(lambda: 60, sync_to_thread=False),
            },
            plugins=[SQLAlchemyPlugin(...)],
        )

Routes registered
-----------------
``GET  /fact_inventory/health``
    Liveness probe — returns HTTP 200 while the process is alive.
    No database dependency; safe to use as a fast liveness check.

``GET  /fact_inventory/ready``
    Readiness probe — returns HTTP 200 when the database is reachable
    (verified with a ``SELECT 1`` query), HTTP 503 otherwise.

``POST /v1/facts``
    Submit system and package facts for the calling host.
"""
