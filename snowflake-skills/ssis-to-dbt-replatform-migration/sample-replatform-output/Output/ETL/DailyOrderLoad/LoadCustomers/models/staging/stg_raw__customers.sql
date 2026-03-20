-- ============================================================
-- Staging: stg_raw__customers
-- Source: contoso_oltp.dbo.customers
-- ============================================================

WITH source AS (
    SELECT * FROM {{ source('contoso_oltp', 'customers') }}
),

renamed AS (
    SELECT
        customer_id,
        customer_name,
        email,
        region,
        CURRENT_TIMESTAMP() AS _loaded_at
    FROM source
)

SELECT * FROM renamed
