-- Customer lifetime value and repeat purchase behavior.
-- Run with: duckdb < sql/02_customer_lifetime_value.sql

SELECT
    customer_unique_id,
    customer_state,
    customer_city,
    first_order_date,
    last_order_date,
    total_orders,
    delivered_orders,
    total_items,
    ROUND(total_payment_value, 2) AS lifetime_value,
    ROUND(avg_order_value, 2) AS avg_order_value,
    ROUND(avg_review_score, 2) AS avg_review_score,
    repeat_customer_flag
FROM read_parquet('data/gold/customer_lifetime_value/*.parquet')
ORDER BY lifetime_value DESC
LIMIT 50;

SELECT
    customer_state,
    COUNT(*) AS customers,
    SUM(CASE WHEN repeat_customer_flag THEN 1 ELSE 0 END) AS repeat_customers,
    ROUND(SUM(total_payment_value), 2) AS total_lifetime_value,
    ROUND(AVG(total_payment_value), 2) AS avg_lifetime_value,
    ROUND(AVG(total_orders), 2) AS avg_orders_per_customer
FROM read_parquet('data/gold/customer_lifetime_value/*.parquet')
GROUP BY customer_state
ORDER BY total_lifetime_value DESC;
