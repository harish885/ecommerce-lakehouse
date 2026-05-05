-- Payment method and installment behavior.
-- Run with: duckdb < sql/06_payment_behavior.sql

SELECT
    payment_type,
    installment_bucket,
    payment_records,
    total_orders,
    ROUND(total_payment_value, 2) AS total_payment_value,
    ROUND(avg_payment_value, 2) AS avg_payment_value,
    ROUND(avg_installments, 2) AS avg_installments,
    ROUND(avg_review_score, 2) AS avg_review_score
FROM read_parquet('data/gold/payment_behavior/*.parquet')
ORDER BY total_payment_value DESC;

SELECT
    payment_type,
    SUM(total_orders) AS total_orders,
    ROUND(SUM(total_payment_value), 2) AS total_payment_value,
    ROUND(AVG(avg_payment_value), 2) AS avg_payment_value
FROM read_parquet('data/gold/payment_behavior/*.parquet')
GROUP BY payment_type
ORDER BY total_payment_value DESC;
