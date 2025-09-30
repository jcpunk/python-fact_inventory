# Host Facts Collection API

A lightweight API service built with Litestar for collecting and storing system information from remote hosts. Designed to handle large-scale concurrency, it provides HTTP endpoint(s) where hosts can submit their system facts and package inventory.

The service includes rate limiting to prevent abuse and can use PostgreSQL with JSON indexing for efficient storage and querying.

## Features

- **Rate Limiting**: Per-IP rate limiting to prevent abuse (configurable interval)
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

4. In version 1 of the application, the database tables are automatically created if missing.

## Configuration

Configuration is managed through environment varibles. These can be loaded programmatically from `.env` files. Set `RUNTIME` to select your `dotenv` config:

```bash
export RUNTIME=production  # loads .env.production
export RUNTIME=testing     # loads .env.testing (default)
```

### Environment Variables

- **DATABASE_URI**: Database connection string (required) - PostgreSQL recommended
- **RATE_LIMIT_MINUTES**: Minutes between allowed submissions per IP (default: 27)
- **DEBUG**: Enable debug mode and OpenAPI docs (default: false)
- **LOG_LEVEL**: Logging level - DEBUG, INFO, WARNING, ERROR (default: INFO)

Create a `.env.{RUNTIME}` file with:

```bash
# Required
DATABASE_URI=postgresql+asyncpg://user:password@localhost/dbname

# Optional (with defaults)
RATE_LIMIT_MINUTES=27
DEBUG=false
LOG_LEVEL=INFO
```

## Running the Application

For production, use a production ASGI server like Uvicorn:

```bash
uvicorn app_factory:create_app --factory --host 0.0.0.0 --port 8000
```

### Data Retention

The tables will grow significantly over time. Consider implementing:

- Table partitioning
- Retention policies to archive/delete old data
- Regular vacuum operations for PostgreSQL

Consult your DBA for production deployment strategies.

### Logging

Logs are sent to `stdout` by default and include:

- Fact submission attempts with client IPs
- Rate limit hits
- Database errors
- Validation failures

## Example client usage:

See `gather_facts.yaml`

## Querying JSON Data (PostgreSQL)

With `GIN` indexes on `JSONB` fields, you can efficiently query facts and build views.

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
