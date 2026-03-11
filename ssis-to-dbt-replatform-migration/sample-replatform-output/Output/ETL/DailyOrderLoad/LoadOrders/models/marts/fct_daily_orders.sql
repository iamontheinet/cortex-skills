-- ============================================================
-- Mart: fct_daily_orders
-- Final fact table for daily order aggregates
-- Materialization: incremental
-- ============================================================

{{
  config(
    materialized='incremental',
    unique_key='order_date',
    incremental_strategy='merge'
  )
}}

WITH enriched AS (
    SELECT * FROM {{ ref('int_orders_enriched') }}
    {% if is_incremental() %}
    WHERE order_date >= (SELECT MAX(order_date) FROM {{ this }})
    {% endif %}
),

daily_agg AS (
    SELECT
        order_date,
        COUNT(DISTINCT order_id) AS total_orders,
        COUNT(DISTINCT customer_id) AS unique_customers,
        SUM(total_amount) AS gross_revenue,
        SUM(line_item_count) AS total_line_items,
        AVG(total_amount)::NUMBER(18,2) AS avg_order_value,
        CURRENT_TIMESTAMP() AS _loaded_at
    FROM enriched
    GROUP BY order_date
)

SELECT * FROM daily_agg
