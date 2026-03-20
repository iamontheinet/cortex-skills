-- ============================================================
-- Macro: m_inventory_helpers
-- Helper macros for inventory calculations
-- ============================================================

{% macro calculate_reorder_point(product_id, safety_stock_days=7) %}

    SELECT AVG(daily_usage) * {{ safety_stock_days }}
    FROM {{ ref('stg_raw__inventory') }}
    WHERE product_id = '{{ product_id }}'

{% endmacro %}
