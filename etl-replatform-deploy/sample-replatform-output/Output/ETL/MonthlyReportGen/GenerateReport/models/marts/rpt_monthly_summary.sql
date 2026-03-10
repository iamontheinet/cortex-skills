-- ============================================================
-- Mart: rpt_monthly_summary
-- Monthly executive summary report
-- Materialization: table (full refresh each month)
-- ============================================================

{{
  config(
    materialized='table'
  )
}}

WITH daily_data AS (
    SELECT * FROM {{ ref('stg_raw__transactions') }}
),

monthly_agg AS (
    SELECT
        DATE_TRUNC('month', order_date)::DATE AS report_month,
        SUM(total_orders) AS total_orders,
        SUM(gross_revenue)::NUMBER(18,2) AS total_revenue,
        AVG(gross_revenue)::NUMBER(18,2) AS avg_daily_revenue,
        MAX(gross_revenue)::NUMBER(18,2) AS peak_daily_revenue,
        MIN(gross_revenue)::NUMBER(18,2) AS lowest_daily_revenue,
        COUNT(DISTINCT order_date) AS business_days,
        SUM(unique_customers) AS total_customer_visits,
        CURRENT_TIMESTAMP() AS generated_at
    FROM daily_data
    GROUP BY DATE_TRUNC('month', order_date)
)

SELECT * FROM monthly_agg
