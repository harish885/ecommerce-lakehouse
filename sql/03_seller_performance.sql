-- Seller performance leaderboard.
-- Run with: duckdb < sql/03_seller_performance.sql

SELECT
    seller_id,
    seller_state,
    seller_city,
    total_orders,
    total_items_sold,
    unique_products,
    unique_customers,
    ROUND(product_revenue, 2) AS product_revenue,
    ROUND(freight_revenue, 2) AS freight_revenue,
    ROUND(total_value, 2) AS total_value,
    ROUND(avg_item_price, 2) AS avg_item_price
FROM read_parquet('data/gold/seller_performance/*.parquet')
ORDER BY product_revenue DESC
LIMIT 50;

SELECT
    seller_state,
    COUNT(*) AS sellers,
    SUM(total_orders) AS total_orders,
    ROUND(SUM(product_revenue), 2) AS product_revenue,
    ROUND(AVG(total_orders), 2) AS avg_orders_per_seller
FROM read_parquet('data/gold/seller_performance/*.parquet')
GROUP BY seller_state
ORDER BY product_revenue DESC;
