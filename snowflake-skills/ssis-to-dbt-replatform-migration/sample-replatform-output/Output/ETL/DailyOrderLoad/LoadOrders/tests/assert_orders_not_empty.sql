-- ============================================================
-- Test: assert_orders_not_empty
-- Ensures the daily orders fact table is populated
-- ============================================================

SELECT COUNT(*) AS row_count
FROM {{ ref('fct_daily_orders') }}
HAVING COUNT(*) = 0
