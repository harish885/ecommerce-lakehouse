# Azure Deployment Guide

This project deploys the Olist lakehouse into Azure using a low-cost student-account stack.

## Current Azure Status

| Item | Status |
|---|---|
| Subscription | `Azure for Students` |
| Tenant | `Universita Cattolica Sacro Cuore - ICATT` |
| Resource group | Created: `rg-ecommerce-lakehouse-dev` |
| Resource group region | `westeurope` |
| Microsoft.Storage provider | Registered |
| Storage account | Blocked by tenant region policy |
| Planned storage account | `stecomlakehousehb` |
| Planned ADLS Gen2 file system | `olist-lakehouse` |

## Policy Blocker

The university tenant currently has conflicting region restrictions for Storage Account
deployment:

- Subscription-level policy allows: `uaenorth`, `polandcentral`, `spaincentral`,
  `switzerlandnorth`, `austriaeast`
- Management-group policy allows: `westeurope`, `italynorth`

Because there is no overlapping region between the two policies, Azure blocks Storage Account
creation in every tested region.

Admin request:

```text
Please allow Storage Account deployment for my Azure for Students subscription in at least one
common region, preferably italynorth or westeurope, or update the management group/subscription
location policies so there is one overlapping allowed region for Microsoft.Storage/storageAccounts.

Project resource group:
rg-ecommerce-lakehouse-dev

Target resource type:
Microsoft.Storage/storageAccounts

Reason:
I need to create an ADLS Gen2 StorageV2 account with hierarchical namespace enabled for an
academic Azure data engineering lakehouse project.
```

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
az account set --subscription "Azure for Students"

az group create \
  --name rg-ecommerce-lakehouse-dev \
  --location westeurope

az provider register --namespace Microsoft.Storage

# This command is currently blocked until the region policy conflict is fixed.
az storage account create \
  --name stecomlakehousehb \
  --resource-group rg-ecommerce-lakehouse-dev \
  --location italynorth \
  --sku Standard_LRS \
  --kind StorageV2 \
  --hns true \
  --min-tls-version TLS1_2 \
  --allow-blob-public-access false

az storage fs create \
  --account-name stecomlakehousehb \
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
abfss://olist-lakehouse@stecomlakehousehb.dfs.core.windows.net/raw/olist/
```

## Next Azure Milestones

1. Point the Bronze pipeline at ADLS Raw and write Bronze Parquet to ADLS.
2. Point Silver and Gold outputs at ADLS paths.
3. Add Azure Data Factory orchestration.
4. Add Synapse Serverless SQL views over Gold Parquet.
5. Connect Power BI to Synapse Serverless or Gold exports.
