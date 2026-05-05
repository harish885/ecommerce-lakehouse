# Architecture Overview

## Platform Design

This project implements the **Medallion Architecture** on **Azure Data Lake Storage Gen2**.
Data flows through four progressive quality layers before reaching the analytics and reporting layer.

## Azure Infrastructure

| Resource | Name | Purpose |
|---|---|---|
| Resource Group | rg-ecommerce-lakehouse-dev | Container for all Azure resources |
| Storage Account | adlsecomlakehousedev | ADLS Gen2 with hierarchical namespace enabled |
| Container | olist-lakehouse | Root container for all data layers |
| Region | West Europe | Closest to Milan, lowest latency |

## Layer Descriptions

### Raw Layer
- **Path:** `raw/olist/{table}/`
- **Format:** Original CSV files
- **Rule:** Never modified, ever
- **Purpose:** Immutable source of truth, audit and recovery

### Bronze Layer
- **Path:** `bronze/olist/{table}/ingestion_date=YYYY-MM-DD/`
- **Format:** Parquet
- **Added columns:** `ingestion_timestamp`, `source_file_name`, `batch_id`, `ingestion_date`
- **Purpose:** Efficient columnar storage with full ingestion audit trail
- **Partitioning:** Hive-style by `ingestion_date` — allows Spark/Synapse to filter by date without full scan

### Silver Layer
- **Path:** `silver/olist/{table}/`
- **Format:** Parquet
- **Transformations:** Type casting, null handling, deduplication, string standardization
- **Rejected records:** Written to `rejected/olist/{table}/` with failure reason column
- **Purpose:** Trusted, clean data that analysts and dashboards can rely on

### Gold Layer
- **Path:** `gold/olist/{table}/`
- **Format:** Parquet
- **Content:** Pre-aggregated, business-ready analytics tables
- **Purpose:** Direct input to Power BI and SQL analytics — answers real business questions

## Data Flow Diagram

```
[Kaggle Olist CSV Files]
         │
         ▼
[Raw Zone — ADLS Gen2]         ← Never modified
         │
         ▼
[Bronze Layer — Parquet]       ← + ingestion metadata
         │
         ▼
[Data Quality Checks]
    │           │
  Pass         Fail
    │           │
    ▼           ▼
[Silver]   [Rejected/]         ← Failed records stored with reason
    │
    ▼
[Gold Layer — Aggregated]
    │           │
    ▼           ▼
[DuckDB SQL] [Power BI]
```

## Orchestration Design

In production, **Azure Data Factory** would orchestrate each layer transition:
- Parameterized pipelines (table name, ingestion date, batch ID)
- ForEach activity iterating over all 9 tables
- Linked Service connecting ADF to ADLS Gen2
- Pipeline triggers on a daily schedule
- Failure alerts and retry logic

In this project, Python scripts replicate identical logic locally, with the same
parameterization pattern — making migration to ADF straightforward.

## Cost Control

| Service | Usage | Estimated Cost |
|---|---|---|
| ADLS Gen2 | ~500 MB data | ~$0.01/month |
| Azure Data Factory | ~20 pipeline runs | ~$0.20 total |
| Databricks | Not used — local PySpark | $0 |
| Synapse Serverless | Not used — local DuckDB | $0 |
| Power BI Desktop | Local desktop app | $0 |
| GitHub Actions | Public repo | $0 |
