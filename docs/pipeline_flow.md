# Pipeline Flow

## Overview

The pipeline runs in three sequential stages. Each stage reads from the previous layer
and writes to the next. All stages are idempotent — running them twice produces the same result.

---

## Stage 1: Bronze Ingestion (`src/ingestion/bronze_ingestion.py`)

**Input:** `data/raw/*.csv` (9 CSV files)
**Output:** `data/bronze/{table}/ingestion_date=YYYY-MM-DD/*.parquet`
**Log:** `logs/bronze_ingestion_log.csv`

### What it does
1. Reads each CSV from `data/raw/`
2. Validates file exists and is not empty
3. Adds metadata columns: `ingestion_timestamp`, `source_file_name`, `batch_id`, `ingestion_date`
4. Writes output as Parquet partitioned by `ingestion_date`
5. Logs row counts, status, and any errors per table

### Metadata columns added

| Column | Description | Example |
|---|---|---|
| `ingestion_timestamp` | Exact datetime of ingestion | `2026-05-05 21:00:00` |
| `source_file_name` | Original CSV filename | `olist_orders_dataset.csv` |
| `batch_id` | Unique batch identifier | `batch_20260505_001` |
| `ingestion_date` | Date partition value | `2026-05-05` |

---

## Stage 2: Silver Transformation (`src/transformation/silver_transformations.py`)

**Input:** `data/bronze/{table}/ingestion_date=*/*.parquet`
**Output:** `data/silver/{table}/*.parquet`
**Rejected:** `data/rejected/{table}/*.parquet`
**Log:** `logs/data_quality_report.csv`

### What it does per table
1. Reads latest Bronze partition
2. Casts columns to correct data types
3. Standardizes string columns (lowercase, strip whitespace)
4. Removes exact duplicate rows
5. Applies data quality rules
6. Splits records into valid → Silver and invalid → Rejected
7. Writes data quality report

---

## Stage 3: Gold Transformation (`src/transformation/gold_transformations.py`)

**Input:** `data/silver/{table}/*.parquet` (multiple tables joined)
**Output:** `data/gold/{table}/*.parquet`

### Gold tables produced

| Table | Source Tables | Business Question |
|---|---|---|
| `daily_sales` | orders, order_items, payments | Revenue per day |
| `monthly_revenue` | orders, order_items, payments | Revenue trend by month |
| `customer_lifetime_value` | customers, orders, payments | Who are the best customers? |
| `product_performance` | order_items, products, category_translation | Which products sell best? |
| `seller_performance` | order_items, sellers, orders | Which sellers perform well? |
| `delivery_delay_analysis` | orders, order_items, sellers | Where are deliveries late? |
| `payment_behavior` | payments | How do customers pay? |
| `review_score_analysis` | reviews, orders | What drives satisfaction? |
| `regional_sales` | orders, customers, payments | Revenue by state/region |

---

## Running the Full Pipeline

```bash
# Step 1 — Bronze
python src/ingestion/bronze_ingestion.py

# Step 2 — Silver
python src/transformation/silver_transformations.py

# Step 3 — Gold
python src/transformation/gold_transformations.py
```

## Error Handling

| Scenario | Behaviour |
|---|---|
| Source file missing | Log error, skip table, continue pipeline |
| Source file empty | Log warning, skip table, continue pipeline |
| Record fails quality check | Write to `rejected/`, log in DQ report |
| Unexpected column | Log warning, continue with available columns |
