-- ============================================================
-- SnowConvert AI Replatform: DailyOrderLoad Orchestration
-- Source: SSIS Package "DailyOrderLoad.dtsx"
-- Pattern: TASK-based DAG
-- ============================================================

-- Root task: Initialize package variables
CREATE OR REPLACE TASK DailyOrderLoad_root
  WAREHOUSE = ETL_WH
  SCHEDULE = '60 MINUTE'
AS
  CALL UpdateControlVariable('DailyOrderLoad', 'LastRunDate', CURRENT_DATE()::VARCHAR);

-- Task 1: Load orders (Data Flow Task -> dbt project)
CREATE OR REPLACE TASK DailyOrderLoad_LoadOrders
  WAREHOUSE = ETL_WH
  AFTER DailyOrderLoad_root
AS
  EXECUTE DBT PROJECT ETL.LoadOrders;

-- Task 2: Load customers (Data Flow Task -> dbt project)
CREATE OR REPLACE TASK DailyOrderLoad_LoadCustomers
  WAREHOUSE = ETL_WH
  AFTER DailyOrderLoad_LoadOrders
AS
  EXECUTE DBT PROJECT ETL.LoadCustomers;
