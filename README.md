# Azure E-Commerce Lakehouse: End-to-End Data Engineering Platform

[![CI Pipeline](https://github.com/harishbhavandla/ecommerce/actions/workflows/ci.yml/badge.svg)](https://github.com/harishbhavandla/ecommerce/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Azure](https://img.shields.io/badge/Azure-ADLS%20Gen2-0078D4)
![Architecture](https://img.shields.io/badge/Architecture-Medallion-gold)
![License](https://img.shields.io/badge/License-MIT-green)

## Overview

An end-to-end cloud data engineering platform built on **Azure Data Lake Storage Gen2**,
implementing the **Medallion Architecture** (Bronze → Silver → Gold) to transform raw
Brazilian Olist e-commerce data into analytics-ready business intelligence.

This project demonstrates real-world data engineering practices including pipeline design,
data quality validation, Parquet storage, SQL analytics, and Power BI dashboarding.

---

## Architecture

```mermaid
flowchart TD
    A[🗂️ Kaggle Olist CSV Files\n9 tables · ~100K orders] --> B[📥 Raw Zone · ADLS Gen2]
    B --> C[🥉 Bronze Layer · Parquet + Metadata]
    C --> D{Data Quality Checks}
    D -->|Pass| E[🥈 Silver Layer · Cleaned & Validated]
    D -->|Fail| F[🚫 Rejected Records]
    E --> G[🥇 Gold Layer · Business Analytics Tables]
    G --> H[🔍 SQL Analytics · DuckDB]
    G --> I[📊 Power BI Dashboard]
    C --> J[📋 Ingestion Log]
    E --> K[📋 DQ Report]
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Cloud Storage | Azure Data Lake Storage Gen2 |
| Orchestration | Azure Data Factory (design) / Python scripts |
| Processing | Python 3.10, Pandas |
| Storage Format | Apache Parquet |
| SQL Analytics | DuckDB / Azure Synapse Serverless |
| Dashboarding | Power BI Desktop |
| CI/CD | GitHub Actions |
| Version Control | Git / GitHub |

---

## Dataset

**Brazilian Olist E-Commerce Dataset** — 9 related tables, ~100K orders, real marketplace data.

Source: [Kaggle — Olist E-Commerce](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)

| Table | Description | Rows |
|---|---|---|
| customers | Customer info and location | 99,441 |
| orders | Order status and timestamps | 99,441 |
| order_items | Items within each order | 112,650 |
| products | Product catalog | 32,951 |
| sellers | Seller info and location | 3,095 |
| payments | Payment details per order | 103,886 |
| reviews | Customer reviews | 99,224 |
| geolocation | ZIP-code lat/lon data | 1,000,163 |
| product_category_translation | Portuguese → English categories | 71 |

---

## Medallion Layers

| Layer | Description | Format | Location |
|---|---|---|---|
| Raw | Original CSV files, never modified | CSV | `data/raw/` |
| Bronze | Parquet + ingestion metadata | Parquet | `data/bronze/{table}/ingestion_date=` |
| Silver | Cleaned, typed, validated | Parquet | `data/silver/{table}/` |
| Gold | Business analytics tables | Parquet | `data/gold/{table}/` |

---

## Project Structure

```
ecommerce/
├── src/
│   ├── ingestion/          # Bronze layer pipeline
│   ├── transformation/     # Silver and Gold pipelines
│   └── utils/              # Logging and Azure utilities
├── sql/                    # Analytics SQL queries
├── tests/                  # Unit tests (pytest)
├── docs/                   # Architecture and data documentation
├── notebooks/              # Exploration notebooks
├── config/                 # Configuration files
├── logs/                   # Pipeline run logs (generated)
└── .github/workflows/      # CI/CD pipeline
```

---

## How to Run Locally

```bash
# 1. Clone the repository
git clone https://github.com/harishbhavandla/ecommerce.git
cd ecommerce

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Place Olist CSVs in data/raw/

# 5. Run Bronze ingestion
python src/ingestion/bronze_ingestion.py

# 6. Run Silver transformation  (Session 4)
python src/transformation/silver_transformations.py

# 7. Run Gold transformation    (Session 5)
python src/transformation/gold_transformations.py
```

---

## Documentation

- [Architecture Overview](docs/architecture.md)
- [Pipeline Flow](docs/pipeline_flow.md)
- [Data Dictionary](docs/data_dictionary.md)
- [Data Quality Rules](docs/data_quality.md)

---

## Dashboard

*Power BI screenshots — coming in Session 5*

---

## Author

**Harish Bhavandla** — Master's in Data Science for Management, Università Cattolica, Milan
[LinkedIn](https://linkedin.com/in/harishbhavandla) · [GitHub](https://github.com/harishbhavandla)
