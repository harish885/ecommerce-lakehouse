-- Review score, delivery delay, and order value patterns.
-- Run with: duckdb < sql/05_review_analysis.sql

SELECT
    review_score,
    has_comment,
    review_count,
    total_orders,
    ROUND(avg_payment_value, 2) AS avg_payment_value,
    ROUND(avg_delivery_days, 2) AS avg_delivery_days,
    ROUND(avg_delay_days, 2) AS avg_delay_days,
    late_orders,
    late_order_rate_pct
FROM read_parquet('data/gold/review_score_analysis/*.parquet')
ORDER BY review_score, has_comment;

SELECT
    customer_state,
    delay_status,
    total_orders,
    late_orders,
    late_order_rate_pct,
    ROUND(avg_delivery_days, 2) AS avg_delivery_days,
    ROUND(avg_delay_days, 2) AS avg_delay_days,
    ROUND(avg_review_score, 2) AS avg_review_score
FROM read_parquet('data/gold/delivery_delay_analysis/*.parquet')
ORDER BY late_order_rate_pct DESC, total_orders DESC
LIMIT 50;
