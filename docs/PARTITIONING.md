# Table Partitioning

A single `host_facts` table can become a bottleneck when the number of reporting hosts is large (tens of thousands of IP addresses across IPv4 and IPv6). PostgreSQL range partitioning by `updated_at` keeps each partition a manageable size, speeds up retention purges, and lets the query planner skip irrelevant partitions. No PostgreSQL extensions are required.

## Strategy

Partition by **month** on `updated_at`. Each partition holds one calendar month of data. Old partitions can be dropped as a unit instead of row-by-row deletes which avoids bloat and is nearly instantaneous.

## Creating the Partitioned Table

If you are setting up a new deployment, create the table as partitioned from the start. This replaces the auto-created table.

> **Important:** Drop the auto-created table first or prevent auto-creation by setting `create_all=False` in `app_factory.py` once you manage the schema yourself.

```sql
CREATE TABLE host_facts (
    id            UUID         NOT NULL DEFAULT gen_random_uuid(),
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    client_address INET        NOT NULL,
    system_facts  JSONB        NOT NULL DEFAULT '{}',
    package_facts JSONB        NOT NULL DEFAULT '{}',

    PRIMARY KEY (id, updated_at)
) PARTITION BY RANGE (updated_at);
```

> Note: In a partitioned table the partition key (`updated_at`) must be part of the primary key.

### Create Partitions

Create a partition for each month you expect data:

```sql
CREATE TABLE host_facts_2026_01 PARTITION OF host_facts
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');

CREATE TABLE host_facts_2026_02 PARTITION OF host_facts
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');

CREATE TABLE host_facts_2026_03 PARTITION OF host_facts
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');

-- ... continue for future months
```

### Create Indexes on Each Partition

PostgreSQL propagates indexes to new partitions automatically when defined on the parent. Apply these to the parent table:

```sql
CREATE INDEX ON host_facts (created_at DESC);
CREATE INDEX ON host_facts (updated_at DESC);
CREATE INDEX ON host_facts (client_address);
CREATE INDEX ON host_facts (client_address, updated_at);
CREATE INDEX ON host_facts USING gin (system_facts);
CREATE INDEX ON host_facts USING gin (package_facts);
CREATE UNIQUE INDEX ON host_facts (client_address, updated_at);
```

## Automating Partition Creation

Use a system cron job with `psql` to create next month's partition ahead of time:

```bash
# Run on the 25th of each month to create next month's partition
0 0 25 * * psql "service=fact_inventory" -f /etc/fact_inventory/create_partition.sh
```

Where `/etc/fact_inventory/create_partition.sh` contains:

```sql
DO $$
DECLARE
    next_start DATE := date_trunc('month', now() + interval '1 month');
    next_end   DATE := next_start + interval '1 month';
    part_name  TEXT := 'host_facts_' || to_char(next_start, 'YYYY_MM');
BEGIN
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF host_facts FOR VALUES FROM (%L) TO (%L)',
        part_name, next_start, next_end
    );
    RAISE NOTICE 'Created partition %', part_name;
END
$$;
```

## Retention via Partition Drop

Dropping an entire partition is much faster than `DELETE`:

```sql
DROP TABLE IF EXISTS host_facts_2025_01;
```

Schedule this with system cron to drop partitions older than the retention window:

```bash
# Run on the 1st of each month at 04:00 UTC — drop the partition from 6 months ago
0 4 1 * * psql "service=fact_inventory" -f /etc/fact_inventory/drop_old_partition.sh
```

Where `/etc/fact_inventory/drop_old_partition.sh` contains:

```sql
DO $$
DECLARE
    old_start DATE := date_trunc('month', now() - interval '6 months');
    part_name TEXT := 'host_facts_' || to_char(old_start, 'YYYY_MM');
BEGIN
    EXECUTE format('DROP TABLE IF EXISTS %I', part_name);
    RAISE NOTICE 'Dropped partition %', part_name;
END
$$;
```

## Migrating an Existing Table

If you already have data in a non-partitioned `host_facts` table:

1. Rename the existing table:

   ```sql
   ALTER TABLE host_facts RENAME TO host_facts_old;
   ```

2. Create the partitioned table and partitions as shown above.

3. Copy data into the partitioned table:

   ```sql
   INSERT INTO host_facts SELECT * FROM host_facts_old;
   ```

4. Verify row counts match, then drop the old table:

   ```sql
   DROP TABLE host_facts_old;
   ```
