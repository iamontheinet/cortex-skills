-- ============================================================
-- Macro: m_update_control_variable
-- Wraps the UpdateControlVariable procedure call
-- Source: SSIS Expression Task
-- ============================================================

{% macro update_control_variable(package_name, variable_name, variable_value) %}

    CALL UpdateControlVariable(
        '{{ package_name }}',
        '{{ variable_name }}',
        '{{ variable_value }}'
    )

{% endmacro %}
