"""fact_inventory -- ASGI application for collecting and storing system facts.

The fact_inventory application is an ASGI service that accepts system and
package facts from distributed clients, stores them in a database, and
provides operational endpoints for health checks and metrics.

Notes
-----
The application follows a layered architecture with:
- schemas.models providing the database ORM layer,
- schemas.repositories providing the database access layer,
- schemas.domain containing business rules and domain objects,
- v1.services as the application service layer,
- v1.controller handling HTTP request/response translation,
- routes for route registration and middleware assembly.

Examples
--------
The main entry point is ``app_factory.create_app`` which returns a fully
configured Litestar ASGI application suitable for deployment with any ASGI
server such as ``uvicorn``.
"""
