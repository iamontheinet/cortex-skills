-- ============================================================
-- Staging: stg_raw__order_details
-- Source: contoso_oltp.dbo.order_details
-- ============================================================

WITH source AS (
    SELECT * FROM {{ source('contoso_oltp', 'order_details') }}
),

renamed AS (
    SELECT
        order_detail_id,
        order_id,
        product_id,
        quantity::INT AS quantity,
        unit_price::NUMBER(18,2) AS unit_price,
        (quantity * unit_price)::NUMBER(18,2) AS line_total,
        CURRENT_TIMESTAMP() AS _loaded_at
    FROM source
)

SELECT * FROM renamed
