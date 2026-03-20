-- ============================================================
-- SnowConvert AI Replatform: MonthlyReportGen Orchestration
-- Source: SSIS Package "MonthlyReportGen.dtsx"
-- Pattern: TASK-based DAG
-- ============================================================

-- Root task: Initialize monthly report generation
CREATE OR REPLACE TASK MonthlyReportGen_root
  WAREHOUSE = REPORT_WH
  SCHEDULE = 'USING CRON 0 2 1 * * America/New_York'
AS
  CALL UpdateControlVariable('MonthlyReportGen', 'ReportMonth',
    TO_CHAR(DATEADD('month', -1, CURRENT_DATE()), 'YYYY-MM'));

-- Task 1: Generate the monthly report (Data Flow Task -> dbt project)
CREATE OR REPLACE TASK MonthlyReportGen_GenerateReport
  WAREHOUSE = REPORT_WH
  AFTER MonthlyReportGen_root
AS
  EXECUTE DBT PROJECT ETL.GenerateReport;

-- Task 2: Archive old data (Data Flow Task -> dbt project)
CREATE OR REPLACE TASK MonthlyReportGen_ArchiveData
  WAREHOUSE = REPORT_WH
  AFTER MonthlyReportGen_GenerateReport
AS
  EXECUTE DBT PROJECT ETL.ArchiveData;
