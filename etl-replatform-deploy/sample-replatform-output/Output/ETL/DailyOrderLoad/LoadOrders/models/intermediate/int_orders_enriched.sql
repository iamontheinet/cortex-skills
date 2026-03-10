-- ============================================================
-- Intermediate: int_orders_enriched
-- Join orders with line items for aggregation
-- Materialization: ephemeral (not persisted to database)
-- ============================================================

{{
  config(
    materialized='ephemeral'
  )
}}

WITH orders AS (
    SELECT * FROM {{ ref('stg_raw__orders') }}
),

details AS (
    SELECT * FROM {{ ref('stg_raw__order_details') }}
),

enriched AS (
    SELECT
        o.order_id,
        o.customer_id,
        o.order_date,
        o.total_amount,
        COUNT(d.order_detail_id) AS line_item_count,
        SUM(d.line_total) AS calculated_total,
        o._loaded_at
    FROM orders o
    LEFT JOIN details d ON o.order_id = d.order_id
    GROUP BY o.order_id, o.customer_id, o.order_date, o.total_amount, o._loaded_at
)

SELECT * FROM enriched
