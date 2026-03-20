# fact_inventory

ASGI sub-application for collecting and storing system facts gathered by
Ansible (or any compatible tool). The package is intentionally independent of
any specific application factory; the only public API integrators need is the
`route_handlers` list.

The sub-application is completely prefix-agnostic. The host application
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
application. The plugin provides an `AsyncSession` through Litestar's
dependency-injection system, which fact_inventory injects into its handlers
automatically.

## Optional host-application configuration

### Rate limiting (`RateLimitMiddleware`)

Rate limiting is handled by Litestar's built-in `RateLimitMiddleware`.
fact_inventory itself contains no rate-limit logic; the host application is
responsible for applying the middleware to the router:

```python
from litestar import Litestar, Router
from litestar.middleware.rate_limit import RateLimitConfig

rate_limit_config = RateLimitConfig(
    rate_limit=("hour", 1),
    exclude=["/health$", "/ready$"],
)

app = Litestar(
    route_handlers=[
        Router(
            path="/fact_inventory",
            route_handlers=route_handlers,
            middleware=[rate_limit_config.middleware],
        ),
    ],
    plugins=[SQLAlchemyPlugin(...)],
)
```

The bundled application factory reads `RATE_LIMIT_UNIT` (default `hour`) and
`RATE_LIMIT_MAX_REQUESTS` (default `1`) from settings. Health and readiness
probes are excluded from rate limiting.

### `DailyCleanupPlugin`

The `DailyCleanupPlugin` (in `app/fact_inventory/plugins/cleanup.py`)
implements Litestar's `InitPluginProtocol` to run a periodic background task
that deletes host records older than `RETENTION_DAYS` (default `365`). The
cleanup interval is controlled by `CLEANUP_INTERVAL_HOURS` (default `24`).

```python
from app.fact_inventory.plugins import DailyCleanupPlugin

cleanup_plugin = DailyCleanupPlugin(
    cleanup_fn=purge_expired_hosts,
    interval_seconds=24 * 3600,
    name="host-retention-cleanup",
)

app = Litestar(
    plugins=[SQLAlchemyPlugin(...), cleanup_plugin],
    ...
)
```

The plugin is self-contained within the fact_inventory package and uses
`lifespan` context managers — no `on_startup`/`on_shutdown` hooks are needed.

## Routes

The `path` argument of the wrapping `Router` controls the leading path segment
for all routes. Using `path="/fact_inventory"` (as in the examples above)
produces the following endpoints:

| Method | Path                 | Description                                                                                                  |
| ------ | -------------------- | ------------------------------------------------------------------------------------------------------------ |
| `GET`  | `/{prefix}/health`   | Liveness probe - HTTP 200 while the process is alive. No database dependency; safe for fast liveness checks. |
| `GET`  | `/{prefix}/ready`    | Readiness probe - HTTP 200 when the database is reachable (`SELECT 1`), HTTP 503 otherwise.                  |
| `POST` | `/{prefix}/v1/facts` | Submit system and package facts for the calling host.                                                        |

## Size limits

The constants `MAX_JSON_FIELD_BYTES` and `MAX_REQUEST_BODY_BYTES` in
`app/fact_inventory/constants.py` control how large individual JSON fields and
the overall request body may be. Adjust them there if the defaults need
tuning.
