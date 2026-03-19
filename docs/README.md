# Host Facts Collection API

A lightweight API service built with Litestar for collecting and storing system information from remote hosts. Designed to handle large-scale concurrency, it provides HTTP endpoint(s) where hosts can submit their system facts and package inventory.

The service includes rate limiting to prevent abuse and can use PostgreSQL with JSON indexing for efficient storage and querying.

## Features

- **Rate Limiting**: Per-IP rate limiting to prevent abuse (configurable interval)
- **Data Retention**: Background purge of stale records via a stored procedure (configurable, PostgreSQL only)
- **Health Check**: `GET /v1/healthz` endpoint for container orchestrators and load balancers
- **Prometheus Metrics**: `GET /metrics` endpoint for scraping HTTP request metrics
- **OpenTelemetry Tracing**: Automatic distributed tracing spans on every request
- **PostgreSQL Optimized**: Uses `JSONB` fields with `GIN` indexes for efficient querying
- **Async Architecture**: Built on SQLAlchemy async and Litestar for high performance
- **Type Safety**: Full type annotations with Pydantic validation
- **Flexible Storage**: Stores arbitrary JSON data for system and package facts
- **OpenAPI Documentation**: Auto-generated API docs in debug mode
- **IP Validation**: IPv4 and IPv6 address validation
- **Payload Size Limits**: "Configurable" max body size and JSON field size validation

## Server Requirements

- Python 3.12+
- PostgreSQL 16+ (recommended for `JSONB` and `GIN` index performance)
- Required Python packages:
  - `advanced-alchemy`
  - `dotenv`
  - `litestar`
  - `pydantic`
  - `sqlalchemy`
  - `asyncpg` (for PostgreSQL)

## Installation

1. Clone the repository

2. Install dependencies:

```bash
uv sync
```

3. Configure environment variables (see Configuration section)

4. Apply database migrations:

```bash
RUNTIME=production alembic upgrade head
```

See [docs/ALEMBIC.md](docs/ALEMBIC.md) for full migration documentation.

## Configuration

Configuration is managed through environment varibles. These can be loaded programmatically from `.env` files. Set `RUNTIME` to select your `dotenv` config:

```bash
export RUNTIME=production  # loads .env.production
export RUNTIME=testing     # loads .env.testing (default)
```

### Environment Variables

- **DATABASE_URI**: Database connection string (required) - PostgreSQL recommended
- **RATE_LIMIT_MINUTES**: Minutes between allowed submissions per IP (default: 27)
- **RETENTION_DAYS**: Days to keep records before the background purge removes them (default: 0 = disabled, PostgreSQL only)
- **CREATE_ALL**: Auto-create tables on startup, bypassing Alembic (default: false)
- **DB_POOL_SIZE**: Database connection pool size (default: 10, PostgreSQL only)
- **DB_POOL_MAX_OVERFLOW**: Max connections above pool size (default: 20, PostgreSQL only)
- **DB_POOL_TIMEOUT**: Seconds to wait for a connection from the pool (default: 30, PostgreSQL only)
- **ALLOWED_ORIGINS**: Comma-separated list of allowed CORS origins (default: none)
- **DEBUG**: Enable debug mode and OpenAPI docs (default: false)
- **LOG_LEVEL**: Logging level - DEBUG, INFO, WARNING, ERROR (default: INFO)

Create a `.env.{RUNTIME}` file with:

```bash
# Required
DATABASE_URI=postgresql+asyncpg://user:password@localhost/dbname

# Optional (with defaults)
RATE_LIMIT_MINUTES=27
RETENTION_DAYS=0
DB_POOL_SIZE=10
DB_POOL_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30
ALLOWED_ORIGINS=
DEBUG=false
LOG_LEVEL=INFO
```

## Running the Application

### With Docker

```bash
docker build -t fact-inventory .
docker run -p 8000:8000 \
  -e DATABASE_URI=postgresql+asyncpg://user:pass@host/db \
  -e RUNTIME=production \
  fact-inventory
```

The container runs Alembic migrations on startup before starting the server.

### Without Docker

For production, use a production ASGI server like Uvicorn:

```bash
RUNTIME=production alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Data Retention

When `RETENTION_DAYS` is set to a value greater than 0 and the database is PostgreSQL, the application runs an internal background task that periodically calls a stored procedure to remove records whose `updated_at` is older than the retention window. No external scheduler or cron daemon is required. See [docs/RETENTION.md](docs/RETENTION.md) for details on the stored procedure and manual usage.

### Table Partitioning

For large networks (tens of thousands of hosts across IPv4 and IPv6), the `host_facts` table should be range-partitioned by `updated_at`. See [docs/PARTITIONING.md](docs/PARTITIONING.md) for setup instructions and automation with system cron.

### Health Check

The `GET /v1/healthz` endpoint verifies the application can reach the database. Use it as the liveness or readiness probe in your container orchestrator.

### Logging

Logs are sent to `stdout` by default and include:

- Fact submission attempts with client IPs
- Rate limit hits
- Database errors
- Validation failures

## Example client usage:

See `gather_facts.yml`

## Querying JSON Data (PostgreSQL)

With `GIN` indexes on `JSONB` fields, you can efficiently query facts and build views. See [docs/VIEWS.md](docs/VIEWS.md) for ready-to-use `CREATE VIEW` examples covering host overview, package inventory, distribution summary, and stale host detection.

## Security Considerations

- The service does not authenticate clients or limit networks
- Rate limiting is based on IP address (can be bypassed with IP rotation)
- JSON payload size is limited to prevent DoS attacks
- Required fields in requests are in fact mandatory
- Unknown fields in requests are rejected

## Troubleshooting

### Database Connection Issues

Ensure PostgreSQL is running and connection string is correct:

```bash
psql ${DATABASE_URI}
```

### Large Payloads

If submissions fail due to size:

- Check JSON field sizes
- Check total request size
- Review logs for specific error messages
