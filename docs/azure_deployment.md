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

## Next Azure Milestones

1. Point the Bronze pipeline at ADLS Raw and write Bronze Parquet to ADLS.
2. Point Silver and Gold outputs at ADLS paths.
3. Add Azure Data Factory orchestration.
4. Add Synapse Serverless SQL views over Gold Parquet.
5. Connect Power BI to Synapse Serverless or Gold exports.
