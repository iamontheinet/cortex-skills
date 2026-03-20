-- ============================================================
-- Staging: stg_raw__inventory
-- Source: contoso_wms.inventory.inventory_levels
-- ============================================================

WITH source AS (
    SELECT * FROM {{ source('contoso_wms', 'inventory_levels') }}
),

renamed AS (
    SELECT
        product_id,
        warehouse_code,
        quantity_on_hand::INT AS quantity_on_hand,
        last_counted_date::DATE AS last_counted_date,
        CURRENT_TIMESTAMP() AS _loaded_at
    FROM source
)

SELECT * FROM renamed
