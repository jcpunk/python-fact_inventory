# Design

The application follows a layered architecture:

## API

### Routing architecture

All `fact_inventory` route handlers are defined at relative paths with no
prefix baked in. The host application mounts them under a chosen prefix by
wrapping the exported `route_handlers` list in a standard Litestar `Router`:

```python
from litestar import Router
from app.fact_inventory.routes import route_handlers

Router(path="/fact_inventory", route_handlers=route_handlers)
```

The `FACT_INVENTORY_PREFIX` setting (default `fact_inventory`) controls the
prefix used by the bundled application factory, producing the paths shown below.

### Unversioned routes

These operational endpoints are not tied to any API version and have no
database-layer dependencies beyond the readiness probe:

| Method | Path               | Description                                                                                |
| ------ | ------------------ | ------------------------------------------------------------------------------------------ |
| `GET`  | `/{prefix}/health` | Liveness probe — HTTP 200 while the process is alive                                       |
| `GET`  | `/{prefix}/ready`  | Readiness probe — HTTP 200 when the database is reachable (`SELECT 1`), HTTP 503 otherwise |

### /{prefix}/v1

- **Controller Layer** (`v1/controller.py`): HTTP endpoint handlers with request validation. Rate limiting is handled externally by Litestar's `RateLimitMiddleware`; the controller is responsible only for validation and persistence.
- **Service Layer** (`v1/services.py`): Business logic without database specific behavior

#### /{prefix}/v1/facts

**Endpoint**: `POST /{prefix}/v1/facts`

**Content-Type**: `application/json`

**Request Body**:

```json
{
  "system_facts": {},
  "package_facts": {}
}
```

**Response Codes**:

- `201 CREATED`: Facts stored successfully
- `400 BAD REQUEST`: Invalid client address
- `409 CONFLICT`: Database error
- `413 TOO LARGE`: Request is too large
- `429 TOO MANY REQUESTS`: Rate limit exceeded
- `500 INTERNAL SERVER ERROR`: Other errors

**Rate Limiting**:

Rate limiting is handled by Litestar's built-in `RateLimitMiddleware`,
configured on the `fact_inventory` router. Health and readiness probes are
excluded from rate limiting via path patterns. The middleware uses an in-memory
store; rate-limit state resets on server restart.

```
HTTP/1.1 429 Too Many Requests
RateLimit-Limit: 1
RateLimit-Remaining: 0
RateLimit-Reset: <seconds>
```

Standard `RateLimit-*` response headers are included on every response.

##### Example with curl

```bash
curl -X POST http://localhost:8000/fact_inventory/v1/facts \
  -H "Content-Type: application/json" \
  -d '{
    "system_facts": {},
    "package_facts": {}
  }'
```

## Database

For the database layer, objects are kept under **schemas**

### HostFacts:

Clients are organized by the IP address they use to connect to the endpoint and not by any data they provide.

- **Repository Layer** (`repositories.py`): Database specific behavior patterns
- **Model Layer** (`models.py`): Data models
- **API Layer** (`apis.py`): Translation layer from the API to the database objects

#### `host_facts` Table

| Column           | Type        | Description                           |
| ---------------- | ----------- | ------------------------------------- |
| `id`             | UUID        | Primary key (auto-generated)          |
| `created_at`     | TIMESTAMP   | Record creation time (auto-generated) |
| `updated_at`     | TIMESTAMP   | Record update time (auto-generated)   |
| `client_address` | VARCHAR(45) | Client IP address (IPv4/IPv6)         |
| `system_facts`   | JSON        | System facts as JSON                  |
| `package_facts`  | JSON        | Package facts as JSON                 |

#### Indexes

- `ix_host_facts_created_at`: DESC index on row creation timestamp
- `ix_host_facts_updated_at`: DESC index on row update timestamp
- `ix_host_facts_client_address`: Index on client IP
- `ix_host_facts_client_address_updated_at`: Multi column index for quickly finding client update time
- `ix_host_facts_system_facts`: GIN index for PostgreSQL JSON queries, useless on other databases
- `ix_host_facts_package_facts`: GIN index for PostgreSQL JSON queries, useless on other databases

## Plugins

### DailyCleanupPlugin

The `DailyCleanupPlugin` implements Litestar's `InitPluginProtocol` to manage
a periodic background task that enforces data retention. It uses `lifespan`
context managers so startup and shutdown are handled in a single,
self-contained block.

- Runs `purge_expired_hosts()` to delete records with an `updated_at` older
  than `RETENTION_DAYS` (default 365).
- The cleanup interval is controlled by `CLEANUP_INTERVAL_HOURS` (default 24).
- The first cleanup run is deferred until after the first sleep interval,
  so the plugin never blocks application startup.
- Exceptions inside the cleanup function are logged but do not crash the loop;
  the plugin retries on the next interval.

The plugin is self-contained within the `fact_inventory` sub-application
(`app/fact_inventory/plugins/cleanup.py`) and is wired into the host
application by the application factory.
