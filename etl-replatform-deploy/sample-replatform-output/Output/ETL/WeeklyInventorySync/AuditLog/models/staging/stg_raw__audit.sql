-- ============================================================
-- Staging: stg_raw__audit
-- Source: contoso_oltp.dbo.audit_log
-- NOTE: This project is intentionally incomplete
-- ============================================================

WITH source AS (
    SELECT * FROM {{ source('contoso_oltp', 'audit_log') }}
),

renamed AS (
    SELECT
        audit_id,
        event_type,
        event_timestamp::TIMESTAMP_NTZ AS event_timestamp,
        user_name,
        details,
        CURRENT_TIMESTAMP() AS _loaded_at
    FROM source
)

SELECT * FROM renamed
