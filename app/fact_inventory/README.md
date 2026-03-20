# fact_inventory

ASGI sub-application for collecting and storing system facts gathered by
Ansible (or any compatible tool).  The package is intentionally independent of
any specific application factory; the only public API integrators need is the
`route_handlers` list.

The sub-application is completely prefix-agnostic.  The host application
controls the URL namespace by wrapping `route_handlers` in a standard Litestar
`Router` at whatever path it chooses.

## Quick-start

```python
from litestar import Litestar, Router
from advanced_alchemy.extensions.litestar import SQLAlchemyPlugin, SQLAlchemyAsyncConfig
from app.fact_inventory.routes import route_handlers

app = Litestar(
    route_handlers=[
        Router(path="/fact_inventory", route_handlers=route_handlers),
    ],
    plugins=[SQLAlchemyPlugin(config=SQLAlchemyAsyncConfig(...))],
)
```

## Required host-application configuration

### `SQLAlchemyPlugin`

An `advanced_alchemy` SQLAlchemy plugin **must** be registered on the Litestar
application.  The plugin provides an `AsyncSession` through Litestar's
dependency-injection system, which fact\_inventory injects into its handlers
automatically.

## Optional Litestar dependencies

### `rate_limit_minutes` (`int`, default `27`)

Minimum minutes that must elapse between successive fact submissions from the
same client IP address.  fact\_inventory declares this as a
`Dependency(default=27)` on its handler, so it works out of the box.  To
override, register a `Provide` at the application level:

```python
from litestar import Litestar, Router
from litestar.di import Provide

app = Litestar(
    route_handlers=[
        Router(path="/fact_inventory", route_handlers=route_handlers),
    ],
    dependencies={
        "rate_limit_minutes": Provide(lambda: 60, sync_to_thread=False),
    },
    plugins=[SQLAlchemyPlugin(...)],
)
```

## Routes

The `path` argument of the wrapping `Router` controls the leading path segment
for all routes.  Using `path="/fact_inventory"` (as in the examples above)
produces the following endpoints:

| Method | Path                         | Description                                              |
|--------|------------------------------|----------------------------------------------------------|
| `GET`  | `/{prefix}/health`           | Liveness probe - HTTP 200 while the process is alive.  No database dependency; safe for fast liveness checks. |
| `GET`  | `/{prefix}/ready`            | Readiness probe - HTTP 200 when the database is reachable (`SELECT 1`), HTTP 503 otherwise. |
| `POST` | `/{prefix}/v1/facts`         | Submit system and package facts for the calling host.    |

## Size limits

The constants `MAX_JSON_FIELD_BYTES` and `MAX_REQUEST_BODY_BYTES` in
`app/fact_inventory/constants.py` control how large individual JSON fields and
the overall request body may be.  Adjust them there if the defaults need
tuning.
