# Host Facts Collection API

A lightweight API service built with Litestar for collecting and storing system information from remote hosts. Designed to handle large-scale concurrency, it provides HTTP endpoint(s) where hosts can submit their system facts and package inventory.

The service includes rate limiting to prevent abuse and can use PostgreSQL with JSON indexing for efficient storage and querying.

## Features

- **Rate Limiting**: Per-IP rate limiting via Litestar's built-in `RateLimitMiddleware` (configurable unit and max requests)
- **Automatic Data Retention**: Background `DailyCleanupPlugin` purges records older than `RETENTION_DAYS`
- **PostgreSQL Optimized**: Uses `JSONB` fields with `GIN` indexes for efficient querying
- **Async Architecture**: Built on SQLAlchemy async and Litestar for high performance
- **Type Safety**: Full type annotations with Pydantic validation
- **Flexible Storage**: Stores arbitrary JSON data for system and package facts
- **OpenAPI Documentation**: Auto-generated API docs in debug mode
- **IP Validation**: IPv4 and IPv6 address validation
- **Payload Size Limits**: Configurable max body size and JSON field size validation

## Server Requirements

- Python 3.12+
- PostgreSQL 16+ (recommended for `JSONB` and `GIN` index performance)
- Required Python packages:
  - `advanced-alchemy`
  - `litestar`
  - `pydantic`
  - `pydantic-settings`
  - `sqlalchemy`
  - `asyncpg` (for PostgreSQL)

## Installation

1. Clone the repository

2. Install dependencies:

```bash
uv sync
```

3. Configure environment variables (see Configuration section)

4. In version 1 of the application, the database tables are automatically created if missing.

## Configuration

Configuration is managed through environment variables. These can be loaded from `.env` files via `pydantic-settings`. Set `RUNTIME` to select your environment config:

```bash
export RUNTIME=production  # loads .env.production
export RUNTIME=testing     # loads .env.testing (default)
```

### Environment Variables

- **DATABASE_URI**: Database connection string (required) - PostgreSQL recommended
- **APP_NAME**: Application name used in metrics and OpenAPI docs (default: `host_inventory`)
- **FACT_INVENTORY_PREFIX**: URL prefix for the fact_inventory sub-app (default: `fact_inventory`)
- **RATE_LIMIT_UNIT**: Time unit for rate limiting -- `second`, `minute`, `hour`, or `day` (default: `hour`)
- **RATE_LIMIT_MAX_REQUESTS**: Maximum requests allowed per rate limit unit (default: `1`)
- **RETENTION_DAYS**: Days to retain host records before automatic purge (default: `365`)
- **CLEANUP_INTERVAL_HOURS**: Hours between background cleanup runs (default: `24`)
- **CREATE_ALL**: Auto-create tables on startup, bypassing Alembic (default: `true`)
- **DB_POOL_SIZE**: Database connection pool size (default: `10`, PostgreSQL only)
- **DB_POOL_MAX_OVERFLOW**: Max connections above pool size (default: `20`, PostgreSQL only)
- **DB_POOL_TIMEOUT**: Seconds to wait for a connection from the pool (default: `30`, PostgreSQL only)
- **DEBUG**: Enable debug mode and OpenAPI docs (default: `false`)
- **LOG_LEVEL**: Logging level - DEBUG, INFO, WARNING, ERROR (default: `INFO`)

Create a `.env.{RUNTIME}` file with:

```bash
# Required
DATABASE_URI=postgresql+asyncpg://user:password@localhost/dbname

# Optional (with defaults)
RATE_LIMIT_UNIT=hour
RATE_LIMIT_MAX_REQUESTS=1
RETENTION_DAYS=365
CLEANUP_INTERVAL_HOURS=24
CREATE_ALL=true
DB_POOL_SIZE=10
DB_POOL_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30
DEBUG=false
LOG_LEVEL=INFO
```

## Running the Application

For production, use a production ASGI server like Uvicorn:

```bash
uvicorn app.app_factory:create_app --factory --host 0.0.0.0 --port 8000
```

### Data Retention

The application includes an automatic background cleanup task
(`DailyCleanupPlugin`) that periodically purges host records older than
`RETENTION_DAYS` (default 365). The cleanup runs every `CLEANUP_INTERVAL_HOURS`
(default 24). The first run is deferred until after the first interval to avoid
impacting startup.

For additional capacity planning, consider:

- Table partitioning
- Regular vacuum operations for PostgreSQL

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
