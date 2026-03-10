-- ============================================================
-- SnowConvert AI Replatform: Control Variables Table
-- Source: SSIS Package Variables / Configuration
-- ============================================================

CREATE OR REPLACE TRANSIENT TABLE public.control_variables (
    package_name        VARCHAR(256)    NOT NULL,
    variable_name       VARCHAR(256)    NOT NULL,
    variable_value      VARCHAR(4000),
    variable_type       VARCHAR(50)     DEFAULT 'String',
    last_updated        TIMESTAMP_NTZ   DEFAULT CURRENT_TIMESTAMP(),
    updated_by          VARCHAR(256)    DEFAULT CURRENT_USER(),
    CONSTRAINT pk_control_variables PRIMARY KEY (package_name, variable_name)
);

-- Seed initial values from SSIS package configurations
INSERT INTO public.control_variables (package_name, variable_name, variable_value, variable_type)
VALUES
    ('DailyOrderLoad',       'LastRunDate',          '2024-01-01',    'DateTime'),
    ('DailyOrderLoad',       'BatchSize',            '10000',         'Int32'),
    ('DailyOrderLoad',       'SourceConnection',     'CONTOSO_OLTP',  'String'),
    ('WeeklyInventorySync',  'SyncMode',             'INCREMENTAL',   'String'),
    ('WeeklyInventorySync',  'WarehouseCode',        'WH-EAST-01',   'String'),
    ('MonthlyReportGen',     'ReportMonth',          '2024-01',       'String'),
    ('MonthlyReportGen',     'OutputFormat',          'PARQUET',       'String');
