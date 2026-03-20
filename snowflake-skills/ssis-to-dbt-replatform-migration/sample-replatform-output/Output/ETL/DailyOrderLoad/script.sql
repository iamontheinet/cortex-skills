-- ============================================================
-- SnowConvert AI Replatform: Migration Script
-- Source: SSIS Execute SQL Task within DailyOrderLoad.dtsx
-- ============================================================

-- Pre-load cleanup: truncate staging tables before incremental load
TRUNCATE TABLE IF EXISTS staging.stg_raw__orders;
TRUNCATE TABLE IF EXISTS staging.stg_raw__order_details;

-- Set batch control variables
CALL UpdateControlVariable('DailyOrderLoad', 'BatchStartTime', CURRENT_TIMESTAMP()::VARCHAR);
