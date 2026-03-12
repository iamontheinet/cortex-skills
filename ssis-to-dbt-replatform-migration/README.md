# SSIS to dbt Replatform Migration

A [Cortex Code](https://docs.snowflake.com/en/user-guide/cortex-code/cortex-code) skill that validates, deploys, and operationalizes **SnowConvert AI Replatform** output — specifically SSIS packages converted to dbt projects and Snowflake TASKs.

## Background

**SSIS** (SQL Server Integration Services) is Microsoft's legacy ETL tool for moving and transforming data. **SnowConvert AI Replatform** converts SSIS packages into two things:

- **dbt projects** — SQL-based data transformations that run natively in Snowflake. Each SSIS Data Flow Task becomes a dbt project with models, sources, and seeds.
- **Snowflake orchestration SQL** — `CREATE TASK` and `CREATE PROCEDURE` statements that schedule and chain those dbt projects, replacing the SSIS package's control flow.

The conversion also produces an `etl_configuration/` directory with shared infrastructure (tables, UDFs, stored procedures) used across packages.

However, the converted output isn't immediately deployable — it often contains placeholder values, naming mismatches, and other issues that need to be caught and fixed before deploying to Snowflake. That's what this skill does.

## What It Does (5 Phases)

| Phase | Description | Snowflake Access |
|-------|-------------|------------------|
| **1. Scan & Inventory** | Reads the `Output/ETL/` directory and produces a JSON inventory of every package, dbt project, orchestration file, and etl_configuration component | None (read-only) |
| **2. Validate & Fix** | Runs automated checks — placeholders in YAML, project name mismatches, missing files, orphan TASKs, dangling refs, hardcoded schemas, unsupported profiles.yml fields, TASK clause ordering, PROCEDURE-based `EXECUTE DBT PROJECT` (unsupported), partial date casts | None (local file edits only) |
| **3. Deploy** | Deploys to Snowflake in dependency order: etl_configuration objects, source tables (seed or stub), dbt projects (`snow dbt deploy`), orchestration SQL | Writes to Snowflake |
| **4. Smoke Test** | Executes each dbt project build, runs orchestration, checks row counts on output tables | Reads/writes Snowflake |
| **5. Operationalize** | (Optional) Sets up CRON schedules on TASKs and/or monitoring queries | Writes to Snowflake |

Every phase requires explicit user approval before proceeding. Each SQL statement and deploy command is shown for review before execution.

## What It Will NOT Do

- Drop or alter any existing objects not created by this workflow
- Push changes to git or modify files outside the Replatform output directory
- Run anything without showing you the exact command/SQL first
- Continue past any phase without your explicit approval

## Automated Validation Checks

The scanner catches common issues in SnowConvert output before they become deployment failures:

| Category | Severity | What It Catches |
|----------|----------|-----------------|
| `PLACEHOLDER` | ERROR | `<database>`, `<schema>`, `TODO` still in YAML files |
| `NAME_MISMATCH` | ERROR | dbt project folder name doesn't match `dbt_project.yml` name |
| `MISSING_FILE` | ERROR | Missing `sources.yml` or `profiles.yml` |
| `UNSUPPORTED_FIELD` | ERROR | `authenticator`, `private_key_path`, etc. in `profiles.yml` |
| `TASK_SYNTAX` | ERROR | `AFTER` clause before `WAREHOUSE` in `CREATE TASK` |
| `PROC_EXECUTE_DBT` | ERROR | `EXECUTE DBT PROJECT` inside a SQL stored procedure (unsupported by Snowflake) |
| `DANGLING_REF` | WARNING | `EXECUTE DBT PROJECT` references a project not found in inventory |
| `ORPHAN_TASK` | WARNING | Task not chained via `AFTER` (potential DAG break) |
| `SCHEMA_MISMATCH` | WARNING | `etl_configuration/` objects reference `public.` schema |
| `SOURCE_SCHEMA_MISMATCH` | WARNING | `sources.yml` has hardcoded `database` field |
| `ORCH_SCHEMA_PREFIX` | WARNING | Hardcoded schema prefix in `EXECUTE DBT PROJECT` |
| `PROFILES_OVERRIDE` | WARNING | Source-environment connection fields in `profiles.yml` — `role`/`account`/`user` must be real target values (not placeholders); `database`/`schema`/`warehouse` are overridden by CLI flags |
| `ORCH_WAREHOUSE` | WARNING | Hardcoded warehouse name in orchestration SQL |
| `PARTIAL_DATE_CAST` | WARNING | `'{{ var(...) }}'::DATE` fails on partial dates like `YYYY-MM` |

## Prerequisites

- **SnowConvert AI Replatform output** — the `Output/ETL/` folder from a completed conversion
- **Snowflake CLI (`snow`)** — installed and configured with an active connection
- **Python 3.11+** and **uv** package manager
- **Cortex Code** — the skill runs inside Cortex Code sessions

## Installation

### Option 1: Remote (auto-synced)

Add to `~/.snowflake/cortex/skills.json`:

```json
{
  "remote": [
    {
      "source": "https://github.com/Snowflake-Labs/dash-cortex-code-skills",
      "ref": "main",
      "skills": [{ "name": "ssis-to-dbt-replatform-migration" }]
    }
  ]
}
```

### Option 2: Manual

```bash
git clone https://github.com/Snowflake-Labs/dash-cortex-code-skills.git /tmp/cortex-skills
cp -r /tmp/cortex-skills/ssis-to-dbt-replatform-migration \
  ~/.snowflake/cortex/skills/ssis-to-dbt-replatform-migration
```

### Verify

Run `/skill` in Cortex Code to confirm it appears, or invoke directly with `$ssis-to-dbt-replatform-migration`.

## Usage

This skill is invoked automatically by Cortex Code when you mention deploying SnowConvert Replatform output. You can also invoke it directly:

```
$ssis-to-dbt-replatform-migration
```

The scanner CLI can also be used standalone:

```bash
# Scan and inventory
uv run --project <skill-dir> python -m replatform_scanner scan <etl-output-dir> <inventory.json>

# View summary
uv run --project <skill-dir> python -m replatform_scanner summary <inventory.json>

# Run validation
uv run --project <skill-dir> python -m replatform_scanner validate <inventory.json>

# List issues
uv run --project <skill-dir> python -m replatform_scanner issues <inventory.json>
```

## How It Fits in the Migration Workflow

```
  SSIS Packages (.dtsx)
         |
         v
  SnowConvert AI Assessment  ──>  snowconvert-assessment skill
         |                         (pre-migration analysis, wave planning)
         v
  SnowConvert AI Replatform
         |
         v
  Output/ETL/ directory
         |
         v
  ssis-to-dbt-replatform-migration skill  ──>  THIS SKILL
         |                          (validate, deploy, smoke test)
         v
  Deployed Snowflake objects
         |
         v
  dbt-projects-on-snowflake skill
  (ongoing management, scheduling, monitoring)
```

## Sample Replatform Output

The `sample-replatform-output/` directory contains a realistic SnowConvert AI Replatform output for testing — 3 SSIS packages, 5 dbt projects, both orchestration patterns, and intentional issues for the validator to catch. Modeled after the official [ETL Migration documentation](https://docs.snowflake.com/en/migrations/snowconvert-docs/general/user-guide/etl-migration-replatform#output-structure).

Seed CSVs are excluded from the repo. To generate them:

```bash
cd sample-replatform-output
python generate_seeds.py          # 10K customers, 50K orders, etc.
python generate_seeds.py --scale 10  # 10x for stress testing
```

See [`sample-replatform-output/README.md`](sample-replatform-output/README.md) for details.

## Project Structure

```
ssis-to-dbt-replatform-migration/
  SKILL.md                          # Skill definition (loaded by Cortex Code)
  pyproject.toml                    # Python project config
  uv.lock                          # Dependency lockfile
  references/
    phase0-briefing.md              # User-facing overview shown at start
    replatform-output-structure.md  # Expected SnowConvert output structure
    snowflake-sql-patterns.md       # SQL syntax reference for deployment
  scripts/
    replatform_scanner/             # Scanner CLI package
      cli.py                        # CLI entry point
      models/
        inventory.py                # Data models (Inventory, ValidationIssue)
      services/
        scanner_service.py          # File scanning and inventory building
        validator_service.py        # Validation checks and issue detection
  tests/
    conftest.py                     # Test fixtures
    test_scanner.py                 # 78 tests covering all validator checks
  sample-replatform-output/         # Test artifact (see above)
    generate_seeds.py               # Deterministic seed CSV generator
    Output/ETL/                     # 3 packages, 5 dbt projects, etl_configuration
```
