# Architecture Overview

## Platform design

This project implements the **Medallion Architecture** on **Azure Data
Lake Storage Gen2**. Data flows through four progressive quality layers
before reaching the BI layer (Power BI semantic model).

A single `Storage` abstraction in [`src/utils/storage.py`](../src/utils/storage.py)
fronts both the local filesystem (used during development and unit testing)
and ADLS Gen2 (used in CI / production), so each pipeline has a single code
path regardless of where it runs.

## Azure infrastructure

| Resource        | Name                          | Purpose                                       |
|-----------------|-------------------------------|-----------------------------------------------|
| Resource group  | `rg-ecommerce-lakehouse-dev`  | Container for all Azure resources             |
| Storage account | `stecomlakehousehb01`         | ADLS Gen2 with hierarchical namespace enabled |
| File system     | `olist-lakehouse`             | Root container for all data layers            |
| Region          | `westeurope`                  | Closest to Milan, lowest latency              |

## Layer descriptions

### Raw

- **Path**: `raw/olist/`
- **Format**: original CSV files
- **Rule**: never modified — immutable source of truth
- **Purpose**: audit and recovery anchor

### Bronze

- **Path**: `bronze/olist/{table}/ingestion_date=YYYY-MM-DD/`
- **Format**: Apache Parquet
- **Added columns**: `ingestion_timestamp`, `source_file_name`, `batch_id`, `ingestion_date`
- **Partitioning**: Hive-style by `ingestion_date` — enables date-based partition
  pruning in Synapse, Databricks, or Power BI incremental refresh
- **Purpose**: efficient columnar storage with a complete ingestion audit trail

### Silver

- **Path**: `silver/olist/{table}/`
- **Format**: Apache Parquet
- **Transformations**: type casting, null handling, deduplication, string standardisation
- **Rejected records**: written to `rejected/olist/{table}/` with `dq_failure_reason` and
  `dq_rule_id` columns — nothing is silently dropped
- **Purpose**: trusted, clean data that analysts and reports can rely on

### Gold

- **Path**: `gold/olist/{table}/`
- **Format**: Apache Parquet
- **Content**: nine pre-aggregated, business-ready analytics marts
- **Purpose**: direct input to Power BI and DuckDB SQL — answers concrete business questions

## Data flow

```text
[Kaggle Olist CSV files]
         │
         ▼
[Raw zone — ADLS Gen2]            ← never modified
         │
         ▼
[Bronze — Parquet]                ← + ingestion metadata
         │
         ▼
[Data quality checks — 25 rules]
    │           │
   Pass        Fail
    │           │
    ▼           ▼
[Silver]   [Rejected/]            ← failed records stored with reason
    │
    ▼
[Gold — aggregated marts]
    │
    ├──► [DuckDB SQL]             ← ad-hoc analytics
    ├──► [Power BI semantic model]← canonical BI layer
    └──► [Synapse Serverless]     ← optional T-SQL surface
```

## Orchestration

In production a managed orchestrator (Azure Data Factory, Databricks Workflows,
or Airflow on AKS) would chain the three layers, parameterized by table name,
ingestion date, and batch ID, with retry and alerting. This repository ships
**GitHub Actions** as the orchestrator:

- `ci.yml` — lint, format check, unit tests on every push / PR.
- `azure-medallion.yml` — manual `workflow_dispatch` that authenticates to
  Azure via OIDC (no stored secrets) and runs Bronze → Silver → Gold
  against live ADLS Gen2.

The pipeline scripts themselves are environment-agnostic — they take a
`Storage` instance from `get_storage("local" | "azure", config)` and
otherwise share one code path. Migrating to ADF would mean swapping the
orchestrator, not rewriting the pipelines.

## Cost profile

| Service              | Usage                  | Approximate cost |
|----------------------|------------------------|------------------|
| ADLS Gen2            | ~500 MB across layers   | ~$0.01 / month   |
| GitHub Actions       | public repo            | $0               |
| Power BI Desktop     | local Windows app      | $0               |
| Power BI Service     | Pro workspace          | $10 / user / mo  |
| Synapse Serverless   | optional, off by default | pay-per-query  |
| Databricks / ADF     | not used               | $0               |
