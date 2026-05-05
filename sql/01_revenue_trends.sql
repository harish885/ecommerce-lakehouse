-- Revenue trends from Gold daily and monthly tables.
-- Run with: duckdb < sql/01_revenue_trends.sql

SELECT
    order_purchase_month,
    total_orders,
    delivered_orders,
    ROUND(total_payment_value, 2) AS total_revenue,
    ROUND(product_revenue, 2) AS product_revenue,
    ROUND(freight_revenue, 2) AS freight_revenue,
    ROUND(avg_order_value, 2) AS avg_order_value,
    ROUND(revenue_per_customer, 2) AS revenue_per_customer,
    ROUND(avg_review_score, 2) AS avg_review_score
FROM read_parquet('data/gold/monthly_revenue/*.parquet')
ORDER BY order_purchase_month;

SELECT
    order_purchase_date,
    total_orders,
    unique_customers,
    ROUND(total_payment_value, 2) AS total_revenue,
    ROUND(avg_order_value, 2) AS avg_order_value
FROM read_parquet('data/gold/daily_sales/*.parquet')
ORDER BY total_revenue DESC
LIMIT 20;
