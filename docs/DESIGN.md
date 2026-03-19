# Design

The application follows a layered architecture:

## API

### /v1

- **Controller Layer** (`controller.py`): HTTP endpoint handlers with request validation
- **Service Layer** (`services.py`): Business logic without database specific behavior

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

**Rate Limit Response**:

```
Rate limit exceeded. Wait 28 minutes.
```

Headers include `Retry-After` in seconds.

##### Example with curl

```bash
curl -X POST http://localhost:8000/v1/facts \
  -H "Content-Type: application/json" \
  -d '{
    "system_facts": {},
    "package_facts": {},
  }'
```

#### /v1/healthz

**Endpoint**: `GET /v1/healthz`

Returns `200 OK` with `{"detail": "ok"}` when the database is reachable, or `503 SERVICE UNAVAILABLE` when it is not. Intended for container orchestrator health probes.

## Observability

### Prometheus Metrics

The Litestar Prometheus middleware automatically collects HTTP request metrics (count, latency, status codes). The `PrometheusController` exposes a `GET /metrics` endpoint in the standard Prometheus text format for scraping.

### OpenTelemetry Tracing

The Litestar OpenTelemetry middleware adds distributed tracing spans to every request. Connect it to your collector by configuring a `TracerProvider` before the app starts (e.g. via `opentelemetry-sdk` and environment variables like `OTEL_EXPORTER_OTLP_ENDPOINT`).

## Background Tasks

### Data Retention (`retention.py`)

When `RETENTION_DAYS > 0` and the database is PostgreSQL, a background task calls the `purge_stale_host_facts` stored procedure once every 24 hours. The stored procedure is created automatically alongside the `host_facts` table via a DDL event (see `models.py`). No HTTP endpoint is exposed for deletion.

## Database

For the database layer, objects are kept under **schemas**

### HostFacts:

Clients are organized by the IP address they use to connect to the endpoint and not by any data they provide.

- **Repository Layer** (`repositories.py`): Database specific behavior patterns
- **Model Layer** (`models.py`): Data models and DDL (including stored procedures)
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

#### Stored Procedures (PostgreSQL only)

- `purge_stale_host_facts(retention_days integer)`: Deletes rows where `updated_at` is older than the given number of days. Created automatically via DDL event when the table is first created.

#### Example Views

See [VIEWS.md](VIEWS.md) for ready-to-use PostgreSQL views.

#### Partitioning

See [PARTITIONING.md](PARTITIONING.md) for range partitioning by `updated_at`.
