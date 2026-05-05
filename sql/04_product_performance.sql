-- Product and category performance.
-- Run with: duckdb < sql/04_product_performance.sql

SELECT
    product_category_name_english,
    COUNT(DISTINCT product_id) AS products,
    SUM(total_orders) AS total_orders,
    SUM(total_items_sold) AS total_items_sold,
    ROUND(SUM(product_revenue), 2) AS product_revenue,
    ROUND(SUM(freight_revenue), 2) AS freight_revenue,
    ROUND(AVG(avg_item_price), 2) AS avg_item_price
FROM read_parquet('data/gold/product_performance/*.parquet')
GROUP BY product_category_name_english
ORDER BY product_revenue DESC
LIMIT 30;

SELECT
    product_id,
    product_category_name_english,
    total_orders,
    total_items_sold,
    unique_sellers,
    ROUND(product_revenue, 2) AS product_revenue,
    ROUND(avg_item_price, 2) AS avg_item_price
FROM read_parquet('data/gold/product_performance/*.parquet')
ORDER BY product_revenue DESC
LIMIT 50;
