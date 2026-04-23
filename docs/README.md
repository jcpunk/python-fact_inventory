# Fact Inventory

A lightweight API service built with Litestar for collecting and storing system
information from remote hosts. Designed to handle large-scale concurrency, it
provides HTTP endpoint(s) where hosts can submit their system facts and package
inventory.

The service includes rate limiting to prevent abuse and can use PostgreSQL with
JSON indexing for efficient storage and querying.

## Features

- **Rate Limiting**: Per-IP rate limiting (default: 2 requests/hour, configurable) to prevent abuse from chatty clients
- **Automatic Data Retention**: Background task periodically purges records older than `RETENTION_DAYS`
- **Duplicate Fact Pruning**: Background task periodically removes duplicate records per client, keeping the newest `HISTORY_MAX_ENTRIES`
- **PostgreSQL Optimized**: Uses `JSONB` fields with `GIN` indexes for efficient querying (development support for SQLite)
- **Async Architecture**: Built on SQLAlchemy async and Litestar for high-performance concurrent handling
- **Type Safety**: Full type annotations with Pydantic validation and mypy strict mode
- **Flexible Storage**: Stores arbitrary JSON data for system, package, and local facts
- **OpenAPI Documentation**: Auto-generated API documentation (enabled in debug mode only)
- **Payload Size Limits**: Per-field and total request body size limits, both configurable

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

4. Database tables are created automatically on startup when `CREATE_ALL=true` (the default). For production migrations, disable `CREATE_ALL` and use Alembic instead (TODO).

## Configuration

Configuration is managed through environment variables. These can be loaded from
`.env` files via `pydantic-settings`. Set `DEPLOYMENT` to select your environment
config:

```bash
export DEPLOYMENT=production  # loads .env.production
export DEPLOYMENT=testing     # loads .env.testing (default)
```

### Environment Variables

The available options are best reviewed from [../fact_inventory/config/settings.py](../fact_inventory/config/settings.py)

Create a `.env.{DEPLOYMENT}` file with:

```bash
DATABASE_URI=postgresql+asyncpg://user:password@localhost/dbname
```

## Running the Application

The standalone application factory serves routes at `/` (no prefix). For
production, run behind a reverse proxy that maps the `/fact_inventory` prefix to
the ASGI server. See [DEPLOYMENT.md](DEPLOYMENT.md) for nginx and Apache
examples.

### Standalone (development)

```bash
uvicorn fact_inventory.app_factory:create_app --factory --host 0.0.0.0 --port 8000
```

### Background Jobs

The application uses `AsyncBackgroundJobPlugin` to run periodic cleanup tasks:

**Data RetentionCleanup**
Purges records older than `RETENTION_DAYS`. Runs every `RETENTION_CHECK_INTERVAL_HOURS` plus up to `RETENTION_CHECK_JITTER_MINUTES` of random offset to prevent thundering-herd effects across multiple instances.

**Duplicate Fact Pruning**
Removes duplicate records per `client_address`, keeping the newest `HISTORY_MAX_ENTRIES`. Runs every `HISTORY_CHECK_INTERVAL_HOURS` plus up to `HISTORY_CHECK_JITTER_MINUTES` of random offset.

The first run of each job is deferred until after the first interval to avoid impacting
startup.

For additional capacity planning, consider:

- Table partitioning
- Regular vacuum operations for PostgreSQL

### Logging

Logs are sent to `stdout` by default and include:

- Fact submission attempts with client IPs
- Rate limit hits
- Database errors
- Validation failures

## Example client usage

See `gather_facts.yml`

## Querying JSON Data (PostgreSQL)

With `GIN` indexes on `JSONB` fields, you can efficiently query facts and build
views. See [VIEWS.md](VIEWS.md) for ready-to-use `CREATE VIEW` examples
covering host overview, package inventory, distribution summary, and stale host
detection.

## Security Considerations

- The service does not authenticate clients or limit networks
- Rate limiting is based on IP address (can be bypassed with IP rotation)
- **Per-field JSON size limits** prevent DoS attacks from oversized individual fields
- **Total request body size limit** prevents DoS attacks from oversized payloads
- Required fields in requests are in fact mandatory
- Unknown fields in requests are rejected
- **CORS** is not enabled. Clients are server-side scripts (Ansible, curl), not
  browsers. The absence of CORS headers is the correct restrictive default.
- **CSRF** protection is not needed. There are no sessions, cookies, or
  browser-based authentication to protect.

## Troubleshooting

### Database Connection Issues

Ensure PostgreSQL is running and connection string is correct:

```bash
psql "${DATABASE_URI}"
```

### Large Payloads

If submissions fail due to size:

**HTTP 413 Request Entity Too Large** can result from two causes:

1. **Total request body too large** (exceeds `MAX_REQUEST_BODY_MB`, default 13 MB):
   - Increase `MAX_REQUEST_BODY_MB` to allow larger total payloads
   - Ensure `MAX_REQUEST_BODY_MB > 3 x MAX_JSON_FIELD_MB`

2. **Per-field JSON too large** (exceeds `MAX_JSON_FIELD_MB`, default 4 MB):
   - Increase `MAX_JSON_FIELD_MB` to allow larger per-field payloads
   - Review logs for specific field name in error message

Review logs for specific error messages to identify which limit was exceeded.
