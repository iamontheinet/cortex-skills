-- ============================================================
-- SnowConvert AI Replatform: Update Control Variable Procedure
-- Source: SSIS Variable Assignment / Expression Task
-- ============================================================

CREATE OR REPLACE PROCEDURE UpdateControlVariable(
    p_package_name VARCHAR,
    p_variable_name VARCHAR,
    p_variable_value VARCHAR
)
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
BEGIN
    MERGE INTO public.control_variables AS target
    USING (
        SELECT
            :p_package_name  AS package_name,
            :p_variable_name AS variable_name,
            :p_variable_value AS variable_value
    ) AS source
    ON target.package_name = source.package_name
       AND target.variable_name = source.variable_name
    WHEN MATCHED THEN
        UPDATE SET
            variable_value = source.variable_value,
            last_updated = CURRENT_TIMESTAMP(),
            updated_by = CURRENT_USER()
    WHEN NOT MATCHED THEN
        INSERT (package_name, variable_name, variable_value)
        VALUES (source.package_name, source.variable_name, source.variable_value);

    RETURN 'Variable updated: ' || :p_package_name || '.' || :p_variable_name;
END;
$$;
