# SnowConvert AI Replatform Output Structure

Reference document describing the expected output structure from SnowConvert AI's Replatform feature (SSIS-to-dbt conversion).

## Top-Level Structure

```
Output/
  ETL/
    etl_configuration/         # Shared infrastructure (deploy FIRST)
      tables/
        control_variables_table.sql
      functions/
        GetControlVariableUDF.sql
      procedures/
        UpdateControlVariable.sql
    {PackageName}/             # One folder per SSIS package
      {PackageName}.sql        # Orchestration (TASK or PROCEDURE)
      {DataFlowTaskName}/      # One dbt project per Data Flow Task
        dbt_project.yml
        profiles.yml
        models/
          sources.yml
          staging/
            stg_raw__{component}.sql
          intermediate/
            int_{component}.sql
          marts/
            {destination}.sql
        macros/
          m_update_control_variable.sql
          m_update_row_count_variable.sql
        seeds/
        tests/
      script.sql               # (optional) Migrated SQL scripts
    (additional packages...)/
```

## SSIS-to-Snowflake Mapping

| SSIS Concept | Snowflake Equivalent |
|---|---|
| Data Flow Task | dbt project (one per Data Flow Task) |
| Control Flow | Snowflake TASK objects or stored procedures |
| Variables | `control_variables` table + UDFs + dbt variables |
| Containers | Inline conversion within parent TASK/procedure |
| Connection Managers | Snowflake connection config in `profiles.yml` |

## dbt Project Layer Architecture

| Layer | Directory | Materialization | Purpose |
|---|---|---|---|
| Staging | `models/staging/` | View | Clean, type-safe access to source data |
| Intermediate | `models/intermediate/` | Ephemeral | Transformation logic (not persisted) |
| Marts | `models/marts/` | Incremental or Table | Final business-ready output tables |

## Orchestration Patterns

### TASK-based (Standard Packages)

The orchestration SQL creates a DAG of Snowflake TASKs:
- Root task: initialization
- Child tasks: depend on root via `AFTER` clause
- Each child task calls `EXECUTE DBT PROJECT <schema>.<project_name>`

```sql
EXECUTE TASK <schema>.<package_name>;
```

### PROCEDURE-based (Reusable Packages)

The orchestration SQL creates a stored procedure that sequentially executes dbt projects:

```sql
CALL <schema>.<package_name>();
```

## Naming Conventions (Sanitization Rules)

SnowConvert AI applies these rules uniformly:

| Rule | Example |
|---|---|
| Convert to lowercase | `MyPackage` -> `mypackage` |
| Replace invalid chars with `_` | `My-Package Name` -> `my_package_name` |
| Remove consecutive `_` | `my___package` -> `my_package` (except `stg_raw__` prefix) |
| Prefix `t_` if starts with number | `123package` -> `t_123package` |
| Strip quotes/brackets | `[Package]` -> `package` |

## etl_configuration Components

Shared infrastructure required by all orchestrations:

- **control_variables_table.sql**: Transient table storing package variables/parameters
- **GetControlVariableUDF.sql**: UDF to retrieve variable values (references `public.control_variables`)
- **UpdateControlVariable.sql**: Procedure to update variables (references `public.control_variables` via MERGE)

**Schema dependency**: These objects default to `public` schema. If deploying to a different schema, all references must be updated.

## Key Files to Validate Before Deployment

1. **`dbt_project.yml`** - `name` field must match the folder name (used by `EXECUTE DBT PROJECT`)
2. **`sources.yml`** - Database/schema placeholders must be filled with actual values
3. **`profiles.yml`** - Connection details must be configured
4. **Orchestration `.sql`** - `EXECUTE DBT PROJECT` references must match deployed project names
5. **`etl_configuration/*.sql`** - Schema references must match target schema
