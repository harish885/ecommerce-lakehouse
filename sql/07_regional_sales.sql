-- Regional sales and delivery performance.
-- Run with: duckdb < sql/07_regional_sales.sql

SELECT
    customer_state,
    COUNT(DISTINCT customer_city) AS cities,
    SUM(total_orders) AS total_orders,
    SUM(delivered_orders) AS delivered_orders,
    SUM(unique_customers) AS unique_customers,
    ROUND(SUM(total_payment_value), 2) AS total_payment_value,
    ROUND(AVG(avg_order_value), 2) AS avg_order_value,
    ROUND(AVG(avg_review_score), 2) AS avg_review_score,
    ROUND(AVG(avg_delivery_days), 2) AS avg_delivery_days
FROM read_parquet('data/gold/regional_sales/*.parquet')
GROUP BY customer_state
ORDER BY total_payment_value DESC;

SELECT
    customer_state,
    customer_city,
    total_orders,
    unique_customers,
    ROUND(total_payment_value, 2) AS total_payment_value,
    ROUND(avg_order_value, 2) AS avg_order_value,
    late_order_rate_pct
FROM read_parquet('data/gold/regional_sales/*.parquet')
ORDER BY total_payment_value DESC
LIMIT 50;
