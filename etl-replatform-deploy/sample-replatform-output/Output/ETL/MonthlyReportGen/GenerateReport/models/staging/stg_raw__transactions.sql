-- ============================================================
-- Staging: stg_raw__transactions
-- Source: contoso_dw.analytics.fct_daily_orders
-- Reads from the output of prior ETL packages
-- ============================================================

WITH source AS (
    SELECT * FROM {{ source('contoso_dw', 'fct_daily_orders') }}
),

filtered AS (
    SELECT
        order_date,
        total_orders,
        unique_customers,
        gross_revenue,
        avg_order_value,
        _loaded_at
    FROM source
    WHERE order_date >= DATE_TRUNC('month', '{{ var("report_month") }}'::DATE)
      AND order_date < DATEADD('month', 1, DATE_TRUNC('month', '{{ var("report_month") }}'::DATE))
)

SELECT * FROM filtered
