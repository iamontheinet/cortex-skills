-- ============================================================
-- SnowConvert AI Replatform: Get Control Variable UDF
-- Source: SSIS Expression / Variable Lookup
-- ============================================================

CREATE OR REPLACE FUNCTION GetControlVariableUDF(
    p_package_name VARCHAR,
    p_variable_name VARCHAR
)
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
    SELECT variable_value
    FROM public.control_variables
    WHERE package_name = p_package_name
      AND variable_name = p_variable_name
$$;
