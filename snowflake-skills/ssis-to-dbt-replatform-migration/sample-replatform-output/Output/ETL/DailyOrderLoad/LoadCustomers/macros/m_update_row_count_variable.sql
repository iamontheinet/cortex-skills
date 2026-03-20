-- ============================================================
-- Macro: m_update_row_count
-- Updates control variable with row count after load
-- Source: SSIS Row Count Transform
-- ============================================================

{% macro update_row_count(package_name, variable_name, model_name) %}

    {% set row_count_query %}
        SELECT COUNT(*) FROM {{ ref(model_name) }}
    {% endset %}

    {% set results = run_query(row_count_query) %}
    {% set row_count = results.columns[0].values()[0] %}

    {{ update_control_variable(package_name, variable_name, row_count|string) }}

{% endmacro %}
