# Data Retention

When `RETENTION_DAYS` is set to a value greater than 0 and the database is PostgreSQL, the application runs an internal background task that calls a stored procedure to remove stale records once every 24 hours. No external scheduler, cron daemon, or PostgreSQL extension is required.

The stored procedure is created automatically alongside the `host_facts` table via a SQLAlchemy DDL event. It uses the `updated_at` column to decide what is stale — a host that has not checked in within the retention window is removed.

## Configuration

Set `RETENTION_DAYS` in your environment or `.env` file:

```bash
RETENTION_DAYS=90   # purge records not updated in 90 days
RETENTION_DAYS=0    # disable retention (default)
```

## Stored Procedure

The function `purge_stale_host_facts` is created automatically alongside the table on PostgreSQL. It is defined with `CREATE OR REPLACE`, so it is safe to recreate.

You can also call it manually:

```sql
-- Preview what would be removed (90-day retention)
SELECT client_address, updated_at
  FROM host_facts
 WHERE updated_at < (now() - interval '90 days');

-- Run the purge
SELECT purge_stale_host_facts(90);
```

## Vacuum

After large purges the table will contain dead tuples. PostgreSQL autovacuum handles this in most cases, but you may want to run a manual vacuum after the first large cleanup:

```sql
VACUUM ANALYZE host_facts;
```
