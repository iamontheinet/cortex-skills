# ETL Replatform Deploy — What This Skill Does

## Background

**SSIS** (SQL Server Integration Services) is Microsoft's legacy ETL tool
for moving and transforming data. **SnowConvert AI Replatform** converts
SSIS packages into two things:

- **dbt projects** — SQL-based data transformations that run natively in
  Snowflake. Each SSIS Data Flow Task becomes a dbt project with models,
  sources, and seeds.
- **Snowflake orchestration SQL** — CREATE TASK and CREATE PROCEDURE
  statements that schedule and chain those dbt projects, replacing the
  SSIS package's control flow.

The conversion also produces an **etl_configuration/** directory with
shared infrastructure (tables, UDFs, stored procedures) used across
packages.

However, the converted output isn't immediately deployable — it often
contains placeholder values, naming mismatches, and other issues that
need to be caught and fixed first. That's what this skill does.

## What will happen (5 phases):

**Phase 1 — Scan & Inventory** (read-only)
  Reads the Output/ETL/ directory on your local filesystem.
  Produces a JSON inventory file listing every package, dbt project,
  orchestration file, and etl_configuration component found.
  → No Snowflake connection needed. No files are modified.

**Phase 2 — Validate & Fix** (local file edits only)
  Runs validation checks against the inventory:
  - Placeholder values (<database>, <schema>, TODO) still in YAML files
  - dbt project name mismatches (folder name vs dbt_project.yml name)
  - Missing files (sources.yml, profiles.yml)
  - Orphan TASKs (not chained via AFTER)
  - Dangling EXECUTE DBT PROJECT references
  - Hardcoded 'public' schema in etl_configuration
  For each issue found, you choose whether to apply the suggested fix.
  → Edits only the files inside your Replatform output directory.
  → Nothing is sent to Snowflake.

**Phase 3 — Deploy** (writes to Snowflake)
  Deploys to your Snowflake account in this order:
  0. Verify target DATABASE and SCHEMA exist (create if needed, with your permission)
  1. etl_configuration objects (CREATE TABLE, CREATE FUNCTION, CREATE PROCEDURE)
  2. dbt projects (via `snow dbt deploy`)
  3. Orchestration SQL (CREATE TASK / CREATE PROCEDURE)
  → You will be asked for target DATABASE, SCHEMA, and connection name first.
  → Each SQL statement and deploy command is shown for review before execution.

**Phase 4 — Smoke Test** (runs queries in Snowflake)
  Executes each dbt project build and runs the orchestration once.
  Checks row counts on output tables.
  → Executes EXECUTE DBT PROJECT, EXECUTE TASK, and SELECT queries.

**Phase 5 — Operationalize** (optional, writes to Snowflake)
  Sets up CRON schedules on TASKs and/or monitoring queries.
  → Only runs if you opt in.

## What this skill will NOT do:
- Drop or alter any existing objects not created by this workflow
- Push changes to git or modify files outside the Replatform output directory
- Run anything without showing you the exact command/SQL first
- Continue past any phase without your explicit approval
