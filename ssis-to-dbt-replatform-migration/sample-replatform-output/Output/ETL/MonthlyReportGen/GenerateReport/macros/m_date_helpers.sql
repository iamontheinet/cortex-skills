-- ============================================================
-- Macro: m_date_helpers
-- Date utility macros for report generation
-- ============================================================

{% macro get_report_month_start() %}
    DATE_TRUNC('month', '{{ var("report_month") }}'::DATE)
{% endmacro %}

{% macro get_report_month_end() %}
    DATEADD('month', 1, DATE_TRUNC('month', '{{ var("report_month") }}'::DATE))
{% endmacro %}

{% macro format_report_period() %}
    TO_CHAR('{{ var("report_month") }}'::DATE, 'MMMM YYYY')
{% endmacro %}
