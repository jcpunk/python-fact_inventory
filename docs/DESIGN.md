# Design

The application follows a layered architecture:

## API

### Routing architecture

All `fact_inventory` route handlers are defined at relative paths with no
prefix baked in.  The host application mounts them under a chosen prefix by
wrapping the exported `route_handlers` list in a standard Litestar `Router`:

```python
from litestar import Router
from app.fact_inventory.routes import route_handlers

Router(path="/fact_inventory", route_handlers=route_handlers)
```

The `APP_NAME` setting (default `fact_inventory`) controls the prefix used by
the bundled application factory, producing the paths shown below.

### Unversioned routes

These operational endpoints are not tied to any API version and have no
database-layer dependencies beyond the readiness probe:

| Method | Path                    | Description                                          |
|--------|-------------------------|------------------------------------------------------|
| `GET`  | `/{prefix}/health`      | Liveness probe — HTTP 200 while the process is alive |
| `GET`  | `/{prefix}/ready`       | Readiness probe — HTTP 200 when the database is reachable (`SELECT 1`), HTTP 503 otherwise |

### /{prefix}/v1

- **Controller Layer** (`v1/controller.py`): HTTP endpoint handlers with request validation
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

**Rate Limit Response**:

```
Rate limit exceeded. Wait 28 minutes.
```

Headers include `Retry-After` in seconds.

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
