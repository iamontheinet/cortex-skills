# Sample Replatform Output

A realistic SnowConvert AI Replatform output directory for testing the `ssis-to-dbt-replatform-migration` skill. Modeled after the official [ETL Migration documentation](https://docs.snowflake.com/en/migrations/snowconvert-docs/general/user-guide/etl-migration-replatform#output-structure).

## What's Inside

Simulates 3 converted SSIS packages with 5 dbt projects:

| Package | Orchestration | dbt Projects |
|---------|--------------|--------------|
| DailyOrderLoad | TASK DAG | LoadCustomers, LoadOrders |
| MonthlyReportGen | TASK DAG | GenerateReport |
| WeeklyInventorySync | PROCEDURE | SyncInventory, AuditLog |

Plus `etl_configuration/` shared infrastructure (control_variables table, UDF, procedure).

## Intentional Issues (for validator testing)

The sample ships in its "raw SnowConvert output" state with these realistic issues:

- `profiles.yml` files have `<placeholder>` tokens instead of real connection values
- `sources.yml` files have `database: "<database>"` and source-environment schema names
- Orchestration SQL has hardcoded `ETL.` schema prefix and source warehouse names
- `stg_raw__transactions.sql` uses `'{{ var("report_month") }}'::DATE` (fails on partial dates)
- `WeeklyInventorySync.sql` uses `EXECUTE DBT PROJECT` inside a PROCEDURE (unsupported)
- `MonthlyReportGen.sql` references `ETL.ArchiveData` (dangling ref — no matching dbt project)

## Generating Seed Data

The `seeds/` directories are empty in the repo. To generate seed CSV files:

```bash
cd sample-replatform-output
python generate_seeds.py
```

This creates deterministic (`random.seed(42)`) CSV files:
- `customers.csv` — 10,000 rows
- `orders.csv` — 50,000 rows
- `order_details.csv` — ~150,000 rows
- `inventory_levels.csv` — 25,000 rows
- `audit_log.csv` — 50,000 rows
- `fct_daily_orders.csv` — 365 rows

For stress testing, use `--scale N`:

```bash
python generate_seeds.py --scale 10
```
