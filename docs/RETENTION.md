# Data Retention

The application does not delete records on its own. Retention is handled at the database level using a PostgreSQL stored procedure that the application creates automatically when the `host_facts` table is first created (via `create_all=True`). No PostgreSQL extensions are required.

The procedure uses the `updated_at` column to decide what is stale. A host that has not checked in within the retention window is removed.

## Stored Procedure

The function `purge_stale_host_facts` is created automatically alongside the table on PostgreSQL. It is defined with `CREATE OR REPLACE`, so it is safe to recreate.

Test it manually before scheduling:

```sql
-- Preview what would be removed (90-day retention)
SELECT client_address, updated_at
  FROM host_facts
 WHERE updated_at < (now() - interval '90 days');

-- Run the purge
SELECT purge_stale_host_facts(90);
```

## Scheduling with System Cron

Use the system crontab to call the stored procedure on a schedule through `psql`. This requires no PostgreSQL extensions.

### One-liner

```bash
# Run daily at 03:00 UTC — purge records older than 90 days
0 3 * * * psql "postgresql://user:password@localhost/dbname" -c "SELECT purge_stale_host_facts(90);"
```

### With a Connection Service File

If you use a [PostgreSQL connection service file](https://www.postgresql.org/docs/current/libpq-pgservice.html) (`~/.pg_service.conf`):

```bash
0 3 * * * psql "service=fact_inventory" -c "SELECT purge_stale_host_facts(90);"
```

### With Environment Variables

```bash
0 3 * * * PGHOST=localhost PGDATABASE=dbname PGUSER=user PGPASSWORD=password psql -c "SELECT purge_stale_host_facts(90);"
```

### Logging Output

Redirect output to a log file so purge results are captured:

```bash
0 3 * * * psql "service=fact_inventory" -c "SELECT purge_stale_host_facts(90);" >> /var/log/fact_inventory_purge.log 2>&1
```

## Vacuum

After large purges the table will contain dead tuples. PostgreSQL autovacuum handles this in most cases, but you may want to run a manual vacuum after the first large cleanup:

```sql
VACUUM ANALYZE host_facts;
```

Or add it to the same cron entry:

```bash
0 3 * * * psql "service=fact_inventory" -c "SELECT purge_stale_host_facts(90); VACUUM ANALYZE host_facts;"
```
