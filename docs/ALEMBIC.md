# Alembic Database Migrations

This project uses [Alembic](https://alembic.sqlalchemy.org/) to manage database schema changes. Alembic tracks each change as a versioned migration script so that upgrades (and rollbacks) are repeatable and auditable.

## Quick Start

### Apply all migrations

Bring the database up to the latest schema:

```bash
RUNTIME=production alembic upgrade head
```

### Check current version

```bash
RUNTIME=production alembic current
```

### View migration history

```bash
alembic history --verbose
```

## Configuration

Alembic reads the database URL from the `DATABASE_URI` environment variable (loaded via the same `.env.{RUNTIME}` mechanism the application uses). The fallback in `alembic.ini` points at an in-memory SQLite database so that commands like `alembic history` work without a running database.

Set `RUNTIME` to choose the environment, exactly as you would when running the application:

```bash
export RUNTIME=production   # loads .env.production
export RUNTIME=testing      # loads .env.testing (default)
```

## Creating a New Migration

After modifying a model in `app/fact_inventory/schemas/`, generate a migration:

```bash
RUNTIME=production alembic revision --autogenerate -m "describe the change"
```

Review the generated file in `alembic/versions/` — autogenerate is helpful but not perfect. Things to check:

- Custom SQL (stored procedures, triggers) must be added manually.
- PostgreSQL-specific DDL should be guarded with a dialect check:

  ```python
  if op.get_bind().dialect.name == "postgresql":
      op.execute(sa.text("CREATE OR REPLACE FUNCTION ..."))
  ```

- Column type changes involving `advanced_alchemy` types may need manual imports.

Then apply the migration:

```bash
RUNTIME=production alembic upgrade head
```

## Rolling Back

Roll back the most recent migration:

```bash
RUNTIME=production alembic downgrade -1
```

Roll back to a specific revision:

```bash
RUNTIME=production alembic downgrade <revision_id>
```

Roll back everything:

```bash
RUNTIME=production alembic downgrade base
```

## Common Workflows

### Adding a column

1. Add the column to the model in `models.py`.
2. Run `alembic revision --autogenerate -m "add column_name to host_facts"`.
3. Review the generated migration.
4. Run `alembic upgrade head`.

### Adding a stored procedure

1. Create a new migration: `alembic revision -m "add my_function"`.
2. Add the SQL in the `upgrade()` function, guarded by a dialect check.
3. Add the `DROP FUNCTION` in the `downgrade()` function, also guarded.
4. Run `alembic upgrade head`.

### Deploying to production

Run migrations as part of your container entrypoint or deployment pipeline:

```bash
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Or in a Dockerfile entrypoint script:

```bash
#!/bin/sh
set -e
RUNTIME=production alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Testing

Tests use `CREATE_ALL=True` (set in `.env.testing`) which bypasses Alembic and creates tables directly via SQLAlchemy. This keeps tests fast and independent of migration history.

To verify that migrations work against a real database:

```bash
# Start fresh
RUNTIME=testing alembic downgrade base

# Apply all migrations
RUNTIME=testing alembic upgrade head

# Verify the schema is up to date (no pending changes)
RUNTIME=testing alembic check
```

## File Layout

```
alembic.ini              # Alembic configuration
alembic/
├── env.py               # Migration environment (loads DATABASE_URI)
├── script.py.mako       # Template for new migration files
├── README               # Alembic's default readme
└── versions/            # Migration scripts (one per revision)
    └── 47f1bb8ab1df_initial_schema.py
```
