# Example Views

The `fact_inventory` table stores arbitrary JSON in `system_facts`,
`package_facts`, and `local_facts`. PostgreSQL views project frequently
needed fields as queryable columns, eliminating repeated JSONB operator
syntax in SQL.

All examples below are read-only projections that add no storage overhead
and always reflect current data. Create them once, query them like normal
tables.

## Host Overview

A flat view of the most commonly referenced system attributes:

```sql
CREATE OR REPLACE VIEW host_overview AS
SELECT
    client_address,
    updated_at,
    system_facts->>'hostname'                   AS hostname,
    system_facts->>'distribution'                AS distribution,
    system_facts->>'distribution_version'        AS distribution_version,
    system_facts->>'distribution_major_version'  AS distribution_major_version,
    system_facts->>'architecture'                AS architecture,
    system_facts->>'kernel'                      AS kernel,
    system_facts->>'fqdn'                        AS fqdn
FROM fact_inventory;
```

```sql
-- All Fedora hosts
SELECT client_address, hostname, distribution_version
  FROM host_overview
 WHERE distribution = 'Fedora';

-- Hosts not seen in the last 7 days
SELECT client_address, hostname, updated_at
  FROM host_overview
 WHERE updated_at < now() - interval '7 days';
```

## Stale Hosts

Hosts that have not checked in within a given window. Useful for monitoring and alerting:

```sql
CREATE OR REPLACE VIEW stale_hosts AS
SELECT
    client_address,
    system_facts->>'hostname' AS hostname,
    updated_at,
    now() - updated_at        AS time_since_update
FROM fact_inventory
WHERE updated_at < now() - interval '7 days';
```

```sql
SELECT * FROM stale_hosts ORDER BY time_since_update DESC;
```

## Package Inventory

Unnest the `package_facts` JSONB object so each package name becomes its own row. This makes it straightforward to search for a specific package across all hosts:

```sql
CREATE OR REPLACE VIEW package_inventory AS
SELECT
    hf.client_address,
    hf.system_facts->>'hostname' AS hostname,
    pkg.key                      AS package_name,
    pkg.value                    AS package_versions
FROM fact_inventory hf,
     LATERAL jsonb_each(hf.package_facts) AS pkg(key, value);
```

```sql
-- Find every host with openssl installed
SELECT client_address, hostname, package_versions
  FROM package_inventory
 WHERE package_name = 'openssl';

-- Count how many hosts have a given package
SELECT package_name, count(*) AS host_count
  FROM package_inventory
 GROUP BY package_name
 ORDER BY host_count DESC
 LIMIT 20;
```

## Distribution Summary

Aggregate view showing how many hosts run each OS distribution and version:

```sql
CREATE OR REPLACE VIEW distribution_summary AS
SELECT
    system_facts->>'distribution'               AS distribution,
    system_facts->>'distribution_version'        AS version,
    system_facts->>'distribution_major_version'  AS major_version,
    count(*)                                     AS host_count
FROM fact_inventory
GROUP BY
    system_facts->>'distribution',
    system_facts->>'distribution_version',
    system_facts->>'distribution_major_version';
```

```sql
SELECT * FROM distribution_summary ORDER BY host_count DESC;
```

## Network Addresses

If the Ansible `setup` module collects network facts, you can extract interface details:

```sql
CREATE OR REPLACE VIEW host_network AS
SELECT
    client_address,
    system_facts->>'hostname'                        AS hostname,
    system_facts->'default_ipv4'->>'address'         AS default_ipv4,
    system_facts->'default_ipv6'->>'address'         AS default_ipv6,
    system_facts->'default_ipv4'->>'interface'       AS ipv4_interface,
    system_facts->'default_ipv6'->>'interface'       AS ipv6_interface
FROM fact_inventory;
```

```sql
-- Find hosts on a specific subnet
SELECT client_address, hostname, default_ipv4
  FROM host_network
 WHERE default_ipv4 IS NOT NULL
   AND default_ipv4::inet <<= '10.0.0.0/8'::inet;
```

## Notes

- Views are defined once and queried like regular tables.
- Because they read from `fact_inventory` at query time, no extra storage is used.
- For frequently run dashboard queries, consider creating a **materialized view** instead (`CREATE MATERIALIZED VIEW ...`). Materialized views cache results and can be refreshed on a schedule with `REFRESH MATERIALIZED VIEW`.
- The JSON key names used above (`hostname`, `distribution`, etc.) match typical Ansible `setup` module output. Adjust them to match the facts your clients actually submit.
