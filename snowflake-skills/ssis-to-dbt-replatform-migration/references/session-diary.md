# Session Diary

This skill maintains a lightweight diary to track deployment state across sessions, namespaced by Snowflake connection.

## Directory Structure

```
~/.snowflake/cortex/memory/replatform/
└── <connection_name>/
    └── <database>.<schema>.md   # Per-deployment diary
```

## Initialization

At the start of every session, before running any commands:

1. **Get connection name** from user (or detect from active Snowflake CLI connection)
2. **Check for existing diary** at `~/.snowflake/cortex/memory/replatform/<connection>/`
   - If exists: Read to restore context (which packages deployed, fixes applied, current phase)
   - If new: Create after Phase 1 completes

## Diary Template

```markdown
# Replatform: <connection> / <database>.<schema>

## Session: <timestamp>
- **Phase reached**: 3 (Deploy)
- **ETL output dir**: /path/to/Output/ETL/
- **Inventory**: /path/to/replatform_inventory.json

## Packages
| Package | Orchestration | Status |
|---------|--------------|--------|
| DailyOrderLoad | TASK | DEPLOYED |
| MonthlyReportGen | TASK | SMOKE_TESTED |

## dbt Projects
| Project | Package | Deploy Status | Smoke Test |
|---------|---------|--------------|------------|
| LoadCustomers | DailyOrderLoad | DONE | PASS |
| LoadOrders | DailyOrderLoad | DONE | FAIL |

## Fixes Applied
- 5 PLACEHOLDER fixes in profiles.yml/sources.yml
- 3 ORCH_SCHEMA_PREFIX fixes (ETL. → PUBLIC.)

## Issues Remaining
- LoadOrders: fct_daily_orders VARCHAR→DATE type mismatch

## Notes
- <observations, decisions, user preferences>
```

## When to Update

- **After Phase 1**: Create diary with package/project inventory
- **After Phase 2**: Record fixes applied and issues remaining
- **After Phase 3**: Update deploy status per project
- **After Phase 4**: Record smoke test results
- **Session resume**: Read diary, present status summary, ask where to continue
