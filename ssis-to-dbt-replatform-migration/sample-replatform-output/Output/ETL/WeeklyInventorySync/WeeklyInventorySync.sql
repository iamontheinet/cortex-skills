-- ============================================================
-- SnowConvert AI Replatform: WeeklyInventorySync Orchestration
-- Source: SSIS Package "WeeklyInventorySync.dtsx"
-- Pattern: PROCEDURE-based (sequential execution)
-- ============================================================

CREATE OR REPLACE PROCEDURE WeeklyInventorySync()
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
BEGIN
    -- Step 1: Initialize control variables
    CALL UpdateControlVariable('WeeklyInventorySync', 'SyncStartTime', CURRENT_TIMESTAMP()::VARCHAR);

    -- Step 2: Execute inventory sync dbt project
    EXECUTE DBT PROJECT ETL.SyncInventory;

    -- Step 3: Execute audit log dbt project
    EXECUTE DBT PROJECT ETL.AuditLog;

    -- Step 4: Update completion variable
    CALL UpdateControlVariable('WeeklyInventorySync', 'SyncEndTime', CURRENT_TIMESTAMP()::VARCHAR);
    CALL UpdateControlVariable('WeeklyInventorySync', 'SyncStatus', 'COMPLETED');

    RETURN 'WeeklyInventorySync completed successfully';
END;
$$;
