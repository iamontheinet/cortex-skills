-- ============================================================
-- Mart: dim_inventory
-- Inventory dimension with current stock levels
-- Materialization: table (full refresh weekly)
-- ============================================================

{{
  config(
    materialized='table'
  )
}}

WITH inventory AS (
    SELECT * FROM {{ ref('stg_raw__inventory') }}
),

enriched AS (
    SELECT
        product_id,
        warehouse_code,
        quantity_on_hand,
        last_counted_date,
        CASE
            WHEN quantity_on_hand = 0 THEN 'OUT_OF_STOCK'
            WHEN quantity_on_hand < 10 THEN 'LOW_STOCK'
            WHEN quantity_on_hand < 100 THEN 'NORMAL'
            ELSE 'HIGH_STOCK'
        END AS stock_status,
        DATEDIFF('day', last_counted_date, CURRENT_DATE()) AS days_since_count,
        _loaded_at
    FROM inventory
)

SELECT * FROM enriched
