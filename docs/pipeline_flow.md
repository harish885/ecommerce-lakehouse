# Pipeline Flow

## Overview

The pipeline runs in three sequential stages. Each stage reads from the
previous layer and writes to the next. All stages are **idempotent** —
running them twice produces the same result, with the same partition
filenames per `batch_id`.

Each stage takes an `--environment` flag (`local` or `azure`) and uses
that to pick a `Storage` backend. The actual transformation code is
identical in both cases — see [`src/utils/storage.py`](../src/utils/storage.py).

---

## Stage 1 — Bronze ingestion

Script: [`src/ingestion/bronze_ingestion.py`](../src/ingestion/bronze_ingestion.py)

| Direction | Path |
|-----------|------|
| Input     | `raw/olist/*.csv` (9 CSV files) |
| Output    | `bronze/olist/{table}/ingestion_date=YYYY-MM-DD/{table}_{batch_id}.parquet` |
| Run log   | `logs/bronze_ingestion_log.csv` (mirrored to ADLS in `azure` mode) |

What it does:

1. Reads each CSV from the Raw zone via the active `Storage` backend.
2. Validates the file exists and is non-empty.
3. Adds four audit columns: `ingestion_timestamp`, `source_file_name`,
   `batch_id`, `ingestion_date`.
4. Writes Hive-partitioned Parquet to Bronze.
5. Verifies the round-trip by re-reading the file and counting rows.
6. Writes one row per table to the run log.

| Audit column          | Purpose                            | Example                |
|-----------------------|------------------------------------|------------------------|
| `ingestion_timestamp` | Exact datetime of ingestion        | `2026-05-05 21:00:00`  |
| `source_file_name`    | Original CSV filename              | `olist_orders_dataset.csv` |
| `batch_id`            | Unique batch run identifier        | `batch_20260505_46956c` |
| `ingestion_date`      | Hive partition value               | `2026-05-05`           |

---

## Stage 2 — Silver transformation

Script: [`src/transformation/silver_transformations.py`](../src/transformation/silver_transformations.py)

| Direction | Path |
|-----------|------|
| Input     | `bronze/olist/{table}/ingestion_date=*/*.parquet` (latest partition) |
| Output    | `silver/olist/{table}/{table}_clean.parquet` |
| Rejected  | `rejected/olist/{table}/rejected_{table}.parquet` |
| Run log   | `logs/data_quality_report.csv` (mirrored to ADLS in `azure` mode) |

What it does, per table:

1. Locates the most-recent Bronze partition for the table.
2. Drops Bronze audit columns (Silver is concerned with business data).
3. Casts columns to the right types.
4. Standardises strings (lowercase, strip whitespace) and ZIP codes.
5. Removes exact duplicate rows.
6. Applies the data-quality rules — passing rows go to Silver, failing
   rows are written to the Rejected zone with `dq_failure_reason` and
   `dq_rule_id` columns.
7. Writes one row per rule to `data_quality_report.csv`.

The cleaning functions (`clean_customers`, `clean_orders`, …) are pure
functions — they take a DataFrame and return `(clean, rejected)`. The
unit tests in `tests/test_silver_transformations.py` exercise them
directly without any I/O.

---

## Stage 3 — Gold transformation

Script: [`src/transformation/gold_transformations.py`](../src/transformation/gold_transformations.py)

| Direction | Path |
|-----------|------|
| Input     | `silver/olist/{table}/{table}_clean.parquet` (multiple tables joined) |
| Output    | `gold/olist/{table}/{table}.parquet` |
| Run log   | `logs/gold_transformation_log.csv` (mirrored to ADLS in `azure` mode) |

What it does:

1. Reads the eight Silver business tables once.
2. Builds enriched intermediates (`orders_enriched`, `order_items_enriched`)
   that pre-join customers, sellers, products, payments, and reviews.
3. Calls each Gold builder, which is a pure function over the enriched
   intermediates.
4. Writes each Gold mart as a single Parquet file.

| Gold mart                  | Joined sources                                        | Business question                  |
|----------------------------|-------------------------------------------------------|-------------------------------------|
| `daily_sales`              | orders, order_items, payments                         | Revenue per day                    |
| `monthly_revenue`          | orders, order_items, payments, reviews                | Revenue trend by month             |
| `customer_lifetime_value`  | customers, orders, payments                           | Who are the best customers?        |
| `product_performance`      | order_items, products, category_translation, sellers  | Which products sell best?          |
| `seller_performance`       | order_items, sellers, orders, customers               | Which sellers perform well?        |
| `delivery_delay_analysis`  | orders, customers                                     | Where are deliveries late?         |
| `payment_behavior`         | payments, orders                                      | How do customers pay?              |
| `review_score_analysis`    | reviews, orders                                       | What drives satisfaction?          |
| `regional_sales`           | orders, customers, payments, reviews                  | Revenue by city / state            |

---

## Running the pipeline

Local:

```bash
python -m src.ingestion.bronze_ingestion
python -m src.transformation.silver_transformations
python -m src.transformation.gold_transformations
```

Azure:

```bash
az login
python -m src.ingestion.bronze_ingestion             --environment azure
python -m src.transformation.silver_transformations  --environment azure
python -m src.transformation.gold_transformations    --environment azure
```

---

## Error handling

| Scenario                     | Behaviour                                              |
|------------------------------|--------------------------------------------------------|
| Source file missing          | Log error, skip that table, fail the run at the end    |
| Source file empty            | Log warning, mark `SKIPPED`, continue                  |
| Record fails a quality check | Write to `rejected/`, append to DQ report, continue    |
| Backend write fails          | Log error, mark table `FAILED`, surface in summary     |

Each stage exits with a non-zero status if any of its tables ended in
`FAILED`, so the GitHub Actions workflow (`azure-medallion.yml`) fails
loudly when something goes wrong.
