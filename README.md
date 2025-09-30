# Host Facts Collection API

A RESTful API service built with Litestar for collecting and storing system and package facts from remote hosts. The service includes rate limiting and PostgreSQL storage with JSON indexing.

## Overview

This service provides an HTTP endpoint for hosts to submit their system facts and package information. It's designed to handle large-scale fact collection with built-in protections against spam and database overload.

## Features

- **Rate Limiting**: Per-IP rate limiting to prevent abuse (configurable interval)
- **PostgreSQL Optimized**: Uses JSONB fields with GIN indexes for efficient querying
- **Async Architecture**: Built on SQLAlchemy async and Litestar for high performance
- **Type Safety**: Full type annotations with Pydantic validation
- **Flexible Storage**: Stores arbitrary JSON data for system and package facts
- **OpenAPI Documentation**: Auto-generated API docs in debug mode
- **IP Validation**: IPv4 and IPv6 address validation
- **Payload Size Limits**: "Configurable" max body size and JSON field size validation

## Example usage:

See `gather_facts.yaml`

## Requirements

- Python 3.12+
- PostgreSQL 16+ (recommended for JSONB and GIN index performance)
- Required Python packages:
  - `advanced-alchemy`
  - `dotenv`
  - `litestar`
  - `pydantic`
  - `sqlalchemy[asyncio]`
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

Configuration is managed through environment files. Set `RUNTIME` to select your config:

```bash
export RUNTIME=production  # loads .env.production
export RUNTIME=testing     # loads .env.testing (default)
```

### Required Environment Variables

Create a `.env.{RUNTIME}` file with:

```bash
# Required
DATABASE_URI=postgresql+asyncpg://user:password@localhost/dbname

# Optional (with defaults)
RATE_LIMIT_MINUTES=27
DEBUG=false
LOG_LEVEL=INFO
```

### Configuration Options

- **DATABASE_URI**: Database connection string (required) - PostgreSQL recommended
- **RATE_LIMIT_MINUTES**: Minutes between allowed submissions per IP (default: 27)
- **DEBUG**: Enable debug mode and OpenAPI docs (default: false)
- **LOG_LEVEL**: Logging level - DEBUG, INFO, WARNING, ERROR (default: INFO)

## Running the Application

The application can be run with any ASGI server. For development:

```bash
uv run python -m app.main
```

For production, use a production ASGI server like Uvicorn:

```bash
uvicorn app_factory:create_app --factory --host 0.0.0.0 --port 8000
```

### Logging

Logs include:

- Fact submission attempts with client IPs
- Rate limit hits
- Database errors
- Validation failures

## Architecture

The application follows a layered architecture:

### API

#### /v1

- **Controller Layer** (`controller.py`): HTTP endpoint handlers with request validation
- **Service Layer** (`services.py`): Business logic without database specific behavior

**Endpoint**: `POST /v1/facts`

**Content-Type**: `application/json`

**Request Body**:

```json
{
  "system_facts": {
    "os": "RHEL",
    "version": "8.5",
    "hostname": "server01",
    "architecture": "x86_64"
  },
  "package_facts": {
    "installed": ["vim", "git", "htop"],
    "total_packages": 1247
  }
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
    "system_facts": {"os": "RHEL", "version": "9.2"},
    "package_facts": {"installed": ["httpd", "nginx"]}
  }'
```

### Database

For the database layer, objects are kept under **schemas**

#### HostFacts:

Clients are organized by the IP address they use to connect to the endpoint and not by any data they provide.

- **Repository Layer** (`repositories.py`): Database specific behavior patterns
- **Model Layer** (`models.py`): Data models
- **API Layer** (`apis.py`): Translation layer from the API to the database objects

##### host_facts Table

| Column           | Type        | Description                           |
| ---------------- | ----------- | ------------------------------------- |
| `id`             | UUID        | Primary key (auto-generated)          |
| `created_at`     | TIMESTAMP   | Record creation time (auto-generated) |
| `updated_at`     | TIMESTAMP   | Record update time (auto-generated)   |
| `client_address` | VARCHAR(45) | Client IP address (IPv4/IPv6)         |
| `system_facts`   | JSON        | System facts as JSON                  |
| `package_facts`  | JSON        | Package facts as JSON                 |

##### Indexes

- `ix_host_info_created_at`: DESC index on row creation timestamp
- `ix_host_info_updated_at`: DESC index on row creation timestamp
- `ix_host_info_client_address`: Index on client IP
- `ix_host_info_system_facts`: GIN index for PostgreSQL JSON queries, useless on other databases

##### Data Retention

The `host_facts` table will grow significantly over time. Consider implementing:

- Table partitioning
- Retention policies to archive/delete old data
- Regular vacuum operations for PostgreSQL

Consult your DBA for production deployment strategies.

##### Querying JSON Data (PostgreSQL)

With GIN indexes on JSONB fields, you can efficiently query facts:

```sql
-- Find hosts running RHEL 8.5
SELECT client_address, created_at
FROM host_facts
WHERE system_facts->>'os' = 'RHEL'
  AND system_facts->>'version' = '8.5';

-- Find hosts with specific packages
SELECT client_address
FROM host_facts
WHERE package_facts->'installed' ? 'vim';
```

## Security Considerations

- The service validates IP addresses are actually IP addresses but does not authenticate clients or limit networks
- Rate limiting is based on IP address (can be bypassed with IP rotation)
- JSON payload size is limited to prevent DoS attacks
- Unknown fields in requests are rejected

## Development

### Development Dependencies

Install with development dependencies:

```shell
uv sync --group dev
```

This includes:

- pytest & pytest-asyncio
- httpx (for testing)
- mypy
- ruff
- pre-commit

### Testing

Run tests with pytest:

```shell
uv run pytest
```

### Debug Mode

Enable debug mode to access OpenAPI documentation:

```bash
export DEBUG=true
```

Visit `http://localhost:8000/schema` for the OpenAPI spec or
`http://localhost:8000/schema/swagger` for a UI.

### Code Quality Tools

The project uses pre-commit hooks for code quality:

- ruff: Fast Python linter and formatter
- mypy: Static type checking
- pre-commit-hooks: Standard checks (trailing whitespace, merge conflicts, etc.)
- prettier: Standardize various documentation formatting

Run checks manually:

```shell
# Run all pre-commit hooks
uv run pre-commit install
uv run pre-commit run --all-files

# Run ruff
uv run ruff check .
uv run ruff format .

# Run mypy
uv run mypy app
```

## Troubleshooting

### Database Connection Issues

Ensure PostgreSQL is running and connection string is correct:

```bash
psql ${DATABASE_URI}
```

### Rate Limit Testing

For testing, set a shorter rate limit in your env file:

```bash
RATE_LIMIT_MINUTES=1
```

### Large Payloads

If submissions fail due to size:

- Check JSON field sizes
- Check total request size
- Review logs for specific error messages

### Pre-commit Hook Failures

If commits are blocked by pre-commit:

```bash
# Fix issues automatically where possible
uv run pre-commit run --all-files

# Skip hooks in emergency (not recommended)
git commit --no-verify
```

### Type Checking Errors

Mypy is configured with strict mode. To investigate type issues:

```bash
uv run mypy app --show-error-codes
```

## License

GPL License - See LICENSE file for details
