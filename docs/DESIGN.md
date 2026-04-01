# Design

The application follows a layered architecture within a single `app` package.
There is no separate sub-application; `app` **is** fact_inventory.

## API

### Routing architecture

All route handlers are defined at relative paths. The standalone application
factory (`create_app`) serves them directly at the root (`/`). When embedding
in a larger Litestar application, pass a prefix to `create_router`::

```python
from app.routes import create_router

router = create_router(path="/fact_inventory")
```

### Unversioned routes

These operational endpoints are not tied to any API version and have no
database-layer dependencies beyond the readiness probe:

| Method | Path      | Description                                                                                |
| ------ | --------- | ------------------------------------------------------------------------------------------ |
| `GET`  | `/health` | Liveness probe -- HTTP 200 while the process is alive                                      |
| `GET`  | `/ready`  | Readiness probe -- HTTP 200 when the database is reachable (`SELECT 1`), HTTP 503 otherwise |

### /v1

- **Controller Layer** (`v1/controller.py`): HTTP endpoint handlers with request validation. Rate limiting is handled by Litestar's `RateLimitMiddleware`; the controller is responsible only for validation and persistence.
- **Service Layer** (`v1/services.py`): Business logic without database specific behavior
- **Response Models** (`v1/responses.py`): Pydantic response envelopes for the v1 API

#### /v1/facts

**Endpoint**: `POST /v1/facts`

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
configured in `routes.py`. Health and readiness probes are excluded
from rate limiting via path patterns. The middleware uses an in-memory
store; rate-limit state resets on server restart.

```
HTTP/1.1 429 Too Many Requests
RateLimit-Limit: 2
RateLimit-Remaining: 0
RateLimit-Reset: <seconds>
```

Standard `RateLimit-*` response headers are included on every response.

##### Example with curl

```bash
curl -X POST http://localhost:8000/v1/facts \
  -H "Content-Type: application/json" \
  -d '{
    "system_facts": {},
    "package_facts": {}
  }'
```

## Database

### HostFacts:

Clients are organized by the IP address they use to connect to the endpoint and not by any data they provide.

- **Repository Layer** (`schemas/repositories.py`): Database specific behavior patterns
- **Model Layer** (`schemas/models.py`): Data models
- **API Layer** (`schemas/apis.py`): Translation layer from the API to the database objects

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

The `DailyCleanupPlugin` (`app/cleanup.py`) implements Litestar's
`InitPluginProtocol` to manage a periodic background task that enforces
data retention. It uses `lifespan` context managers so startup and shutdown
are handled in a single, self-contained block.

- Runs `purge_expired_hosts()` to delete records with an `updated_at` older
  than `RETENTION_DAYS` (default 365).
- The cleanup interval is controlled by `CLEANUP_INTERVAL_HOURS` (default 24).
- A configurable jitter (`CLEANUP_JITTER_MINUTES`, default 20) is added to each
  sleep cycle so that cleanup runs do not fire at the exact same wall-clock
  time every day.
- The first cleanup run is deferred until after the first sleep interval,
  so the plugin never blocks application startup.
- Exceptions inside the cleanup function are logged but do not crash the loop;
  the plugin retries on the next interval.
