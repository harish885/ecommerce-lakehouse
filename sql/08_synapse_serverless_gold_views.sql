-- Azure Synapse Serverless SQL views over ADLS Gen2 Gold Parquet.
-- Run this in Synapse Studio against the built-in serverless SQL pool.
-- Power BI can then connect to the ecommerce_lakehouse database and import these views.

IF DB_ID('ecommerce_lakehouse') IS NULL
    CREATE DATABASE ecommerce_lakehouse;
GO

USE ecommerce_lakehouse;
GO

CREATE OR ALTER VIEW dbo.daily_sales AS
SELECT *
FROM OPENROWSET(
    BULK 'https://stecomlakehousehb01.dfs.core.windows.net/olist-lakehouse/gold/olist/daily_sales/daily_sales.parquet',
    FORMAT = 'PARQUET'
) AS rows;
GO

CREATE OR ALTER VIEW dbo.monthly_revenue AS
SELECT *
FROM OPENROWSET(
    BULK 'https://stecomlakehousehb01.dfs.core.windows.net/olist-lakehouse/gold/olist/monthly_revenue/monthly_revenue.parquet',
    FORMAT = 'PARQUET'
) AS rows;
GO

CREATE OR ALTER VIEW dbo.customer_lifetime_value AS
SELECT *
FROM OPENROWSET(
    BULK 'https://stecomlakehousehb01.dfs.core.windows.net/olist-lakehouse/gold/olist/customer_lifetime_value/customer_lifetime_value.parquet',
    FORMAT = 'PARQUET'
) AS rows;
GO

CREATE OR ALTER VIEW dbo.product_performance AS
SELECT *
FROM OPENROWSET(
    BULK 'https://stecomlakehousehb01.dfs.core.windows.net/olist-lakehouse/gold/olist/product_performance/product_performance.parquet',
    FORMAT = 'PARQUET'
) AS rows;
GO

CREATE OR ALTER VIEW dbo.seller_performance AS
SELECT *
FROM OPENROWSET(
    BULK 'https://stecomlakehousehb01.dfs.core.windows.net/olist-lakehouse/gold/olist/seller_performance/seller_performance.parquet',
    FORMAT = 'PARQUET'
) AS rows;
GO

CREATE OR ALTER VIEW dbo.delivery_delay_analysis AS
SELECT *
FROM OPENROWSET(
    BULK 'https://stecomlakehousehb01.dfs.core.windows.net/olist-lakehouse/gold/olist/delivery_delay_analysis/delivery_delay_analysis.parquet',
    FORMAT = 'PARQUET'
) AS rows;
GO

CREATE OR ALTER VIEW dbo.payment_behavior AS
SELECT *
FROM OPENROWSET(
    BULK 'https://stecomlakehousehb01.dfs.core.windows.net/olist-lakehouse/gold/olist/payment_behavior/payment_behavior.parquet',
    FORMAT = 'PARQUET'
) AS rows;
GO

CREATE OR ALTER VIEW dbo.review_score_analysis AS
SELECT *
FROM OPENROWSET(
    BULK 'https://stecomlakehousehb01.dfs.core.windows.net/olist-lakehouse/gold/olist/review_score_analysis/review_score_analysis.parquet',
    FORMAT = 'PARQUET'
) AS rows;
GO

CREATE OR ALTER VIEW dbo.regional_sales AS
SELECT *
FROM OPENROWSET(
    BULK 'https://stecomlakehousehb01.dfs.core.windows.net/olist-lakehouse/gold/olist/regional_sales/regional_sales.parquet',
    FORMAT = 'PARQUET'
) AS rows;
GO
