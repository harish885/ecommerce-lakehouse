# Azure Deployment Guide

This project deploys the Olist lakehouse into Azure using a low-cost student-account stack.

## Current Azure Status

| Item | Status |
|---|---|
| Subscription | `Azure subscription 1` |
| Tenant | `Default Directory` |
| Resource group | Created: `rg-ecommerce-lakehouse-dev` |
| Resource group region | `westeurope` |
| Microsoft.Storage provider | Registered |
| Storage account | Created: `stecomlakehousehb01` |
| ADLS Gen2 file system | Created: `olist-lakehouse` |
| Raw CSV upload | Complete: 9 files in `raw/olist/` |
| Bronze ingestion | Complete: 9 Parquet tables in `bronze/olist/` |
| Silver transformation | Complete: 9 clean Parquet tables in `silver/olist/` |
| Rejected records | Complete: 2 rejected Parquet files in `rejected/olist/` |
| Gold transformation | Complete: 9 analytics Parquet tables in `gold/olist/` |

## Lake Layout

```text
olist-lakehouse/
├── raw/olist/
├── bronze/olist/
├── silver/olist/
├── gold/olist/
├── rejected/olist/
└── logs/
```

## Provisioning Commands

```bash
az account set --subscription "Azure subscription 1"

az group create \
  --name rg-ecommerce-lakehouse-dev \
  --location westeurope

az provider register --namespace Microsoft.Storage

az storage account create \
  --name stecomlakehousehb01 \
  --resource-group rg-ecommerce-lakehouse-dev \
  --location westeurope \
  --sku Standard_LRS \
  --kind StorageV2 \
  --hns true \
  --min-tls-version TLS1_2 \
  --allow-blob-public-access false

az storage fs create \
  --account-name stecomlakehousehb01 \
  --name olist-lakehouse \
  --auth-mode login
```

## Upload Raw Data

After `az login`, run:

```bash
python scripts/upload_raw_to_adls.py
```

The script uploads all CSV files from `data/raw/` to:

```text
abfss://olist-lakehouse@stecomlakehousehb01.dfs.core.windows.net/raw/olist/
```

If the Python upload script cannot access Azure CLI credentials in a sandboxed environment,
upload with Azure CLI:

```bash
for f in data/raw/*.csv; do
  az storage fs file upload \
    --account-name stecomlakehousehb01 \
    --file-system olist-lakehouse \
    --path "raw/olist/$(basename "$f")" \
    --source "$f" \
    --overwrite true \
    --auth-mode login
done
```

Verify Raw files:

```bash
az storage fs file list \
  --account-name stecomlakehousehb01 \
  --file-system olist-lakehouse \
  --path raw/olist \
  --auth-mode login \
  --query "[].{name:name, size:contentLength}" \
  --output table
```

Expected files:

```text
raw/olist/olist_customers_dataset.csv
raw/olist/olist_geolocation_dataset.csv
raw/olist/olist_order_items_dataset.csv
raw/olist/olist_order_payments_dataset.csv
raw/olist/olist_order_reviews_dataset.csv
raw/olist/olist_orders_dataset.csv
raw/olist/olist_products_dataset.csv
raw/olist/olist_sellers_dataset.csv
raw/olist/product_category_name_translation.csv
```

## Run Bronze Ingestion on Azure

Run the Bronze pipeline against ADLS Gen2:

```bash
python src/ingestion/bronze_ingestion.py --environment azure
```

This reads:

```text
abfss://olist-lakehouse@stecomlakehousehb01.dfs.core.windows.net/raw/olist/
```

And writes partitioned Bronze Parquet files to:

```text
abfss://olist-lakehouse@stecomlakehousehb01.dfs.core.windows.net/bronze/olist/{table}/ingestion_date=YYYY-MM-DD/
```

It also uploads the Bronze ingestion log to:

```text
abfss://olist-lakehouse@stecomlakehousehb01.dfs.core.windows.net/logs/bronze_ingestion_log.csv
```

Latest verified run:

```text
Batch ID: batch_20260505_46956c
Tables: 9/9 successful
Rows ingested: 1,550,922
Bronze path: bronze/olist/{table}/ingestion_date=2026-05-05/
```

## Run Silver Transformation on Azure

Run the Silver pipeline against ADLS Gen2:

```bash
python src/transformation/silver_transformations.py --environment azure
```

This reads the latest Bronze partition from:

```text
abfss://olist-lakehouse@stecomlakehousehb01.dfs.core.windows.net/bronze/olist/{table}/
```

And writes clean Silver Parquet files to:

```text
abfss://olist-lakehouse@stecomlakehousehb01.dfs.core.windows.net/silver/olist/{table}/{table}_clean.parquet
```

Rejected records are written to:

```text
abfss://olist-lakehouse@stecomlakehousehb01.dfs.core.windows.net/rejected/olist/{table}/
```

The DQ report is uploaded to:

```text
abfss://olist-lakehouse@stecomlakehousehb01.dfs.core.windows.net/logs/data_quality_report.csv
```

Latest verified run:

```text
Tables: 9/9 successful
Clean Silver rows: 568,954
Rejected rows: 6
Rejected files: rejected_products.parquet, rejected_payments.parquet
DQ rules: 25 PASS
```

## Run Gold Transformation on Azure

Run the Gold pipeline against ADLS Gen2:

```bash
python src/transformation/gold_transformations.py --environment azure
```

This reads Silver Parquet files from:

```text
abfss://olist-lakehouse@stecomlakehousehb01.dfs.core.windows.net/silver/olist/{table}/
```

And writes Gold analytics tables to:

```text
abfss://olist-lakehouse@stecomlakehousehb01.dfs.core.windows.net/gold/olist/{table}/{table}.parquet
```

The Gold run log is uploaded to:

```text
abfss://olist-lakehouse@stecomlakehousehb01.dfs.core.windows.net/logs/gold_transformation_log.csv
```

Latest verified run:

```text
Tables: 9/9 successful
Gold analytics rows: 137,234
Gold path: gold/olist/{table}/{table}.parquet
```

## Next Azure Milestones

1. Add Azure Data Factory orchestration.
2. Add Synapse Serverless SQL views over Gold Parquet.
3. Connect Power BI to Synapse Serverless or Gold exports.
