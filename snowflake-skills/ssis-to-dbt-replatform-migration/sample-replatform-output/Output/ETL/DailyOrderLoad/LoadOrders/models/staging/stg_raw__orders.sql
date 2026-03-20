-- ============================================================
-- Staging: stg_raw__orders
-- Source: contoso_oltp.dbo.orders
-- ============================================================

WITH source AS (
    SELECT * FROM {{ source('contoso_oltp', 'orders') }}
),

renamed AS (
    SELECT
        order_id,
        customer_id,
        order_date::DATE AS order_date,
        total_amount::NUMBER(18,2) AS total_amount,
        CURRENT_TIMESTAMP() AS _loaded_at
    FROM source
)

SELECT * FROM renamed
