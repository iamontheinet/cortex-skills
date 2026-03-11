# Snowflake SQL Patterns for Replatform Deploy

Reference for SQL patterns used during deployment. Loaded when needed in Phase 3.

## Verify Database Exists

```sql
SHOW DATABASES LIKE '<TARGET_DATABASE>';
```

If missing, create with user approval:
```sql
CREATE DATABASE <TARGET_DATABASE>;
```

## Verify Schema Exists

```sql
USE DATABASE <TARGET_DATABASE>;
SHOW SCHEMAS LIKE '<TARGET_SCHEMA>' IN DATABASE <TARGET_DATABASE>;
```

If missing, create with user approval:
```sql
CREATE SCHEMA <TARGET_DATABASE>.<TARGET_SCHEMA>;
```

## Set Active Context

```sql
USE DATABASE <TARGET_DATABASE>;
USE SCHEMA <TARGET_DATABASE>.<TARGET_SCHEMA>;
```

## Check If Source Table Exists

```sql
SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_CATALOG = '<TARGET_DATABASE>'
  AND TABLE_SCHEMA = '<TARGET_SCHEMA>'
  AND TABLE_NAME = '<TABLE_NAME>';
```

## Create Stub Table (New Table)

Use `CREATE TABLE IF NOT EXISTS` with all columns typed as `VARCHAR`:

```sql
CREATE TABLE IF NOT EXISTS <TARGET_DATABASE>.<TARGET_SCHEMA>.<TABLE_NAME> (
    <COLUMN1> VARCHAR,
    <COLUMN2> VARCHAR,
    <COLUMN3> VARCHAR
);
```

Get column names from the `columns:` list in `sources.yml`.

## Recreate Stub Table (Existing Table With Wrong Columns)

```sql
CREATE OR REPLACE TABLE <TARGET_DATABASE>.<TARGET_SCHEMA>.<TABLE_NAME> (
    <COLUMN1> VARCHAR,
    <COLUMN2> VARCHAR,
    <COLUMN3> VARCHAR
);
```

**IMPORTANT SQL syntax rules:**
- Use `CREATE TABLE IF NOT EXISTS` for new tables — never `ALTER TABLE ADD COLUMN`
- Use `CREATE OR REPLACE TABLE` when table exists but has wrong columns
- Each column definition separated by commas — no trailing comma after last column
- Do NOT use `ADD COLUMN` syntax — it causes syntax errors in this context
- Always ask user permission before `CREATE OR REPLACE` since it destroys existing data

## Seed From CSV (Preferred Over Stubs)

If seed CSVs exist in the project's `seeds/` directory, prefer seeding:

```bash
snow dbt execute <PROJECT_NAME> "seed" --database <TARGET_DATABASE> --schema <TARGET_SCHEMA>
```

Seeds provide actual test data and land in the target database/schema,
which is where `sources.yml` (with `schema: PUBLIC` and no `database` override) resolves.

## Monitor Task Execution

```sql
SELECT NAME, STATE, ERROR_MESSAGE, SCHEDULED_TIME, COMPLETED_TIME
FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY(
  SCHEDULED_TIME_RANGE_START => DATEADD('hour', -1, CURRENT_TIMESTAMP()),
  RESULT_LIMIT => 50
))
WHERE DATABASE_NAME = '<DATABASE>'
  AND SCHEMA_NAME = '<SCHEMA>'
ORDER BY SCHEDULED_TIME DESC;
```
