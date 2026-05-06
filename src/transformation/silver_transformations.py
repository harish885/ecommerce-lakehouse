"""
Silver Layer Transformation Pipeline
======================================
Reads Bronze Parquet files, applies cleaning, type casting, deduplication,
and data quality checks per table. Valid records → silver/, invalid → rejected/.
Supports local filesystem and Azure Data Lake Storage Gen2.

Usage:
    python src/transformation/silver_transformations.py
    python src/transformation/silver_transformations.py --environment azure

Output:
    data/silver/{table}/{table}_clean.parquet
    data/rejected/{table}/rejected_{table}.parquet
    abfss://{container}@{account}.dfs.core.windows.net/silver/olist/{table}/...
    logs/data_quality_report.csv
"""

import argparse
import io
import os
import sys
from datetime import datetime

import pandas as pd
import yaml
from loguru import logger

from azure.core.exceptions import ResourceExistsError
from azure.identity import AzureCliCredential
from azure.storage.filedatalake import DataLakeServiceClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from src.utils.logger import setup_logger, write_dq_log

VALID_STATES = [
    "AC",
    "AL",
    "AP",
    "AM",
    "BA",
    "CE",
    "DF",
    "ES",
    "GO",
    "MA",
    "MT",
    "MS",
    "MG",
    "PA",
    "PB",
    "PR",
    "PE",
    "PI",
    "RJ",
    "RN",
    "RS",
    "RO",
    "RR",
    "SC",
    "SP",
    "SE",
    "TO",
]
VALID_ORDER_STATUSES = [
    "delivered",
    "shipped",
    "canceled",
    "unavailable",
    "processing",
    "invoiced",
    "approved",
    "created",
]
VALID_PAYMENT_TYPES = ["credit_card", "boleto", "voucher", "debit_card", "not_defined"]


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────


def load_config(path="config/config.yaml"):
    with open(path) as f:
        return yaml.safe_load(f)


def get_adls_file_system_client(azure_config: dict):
    account_name = azure_config["storage_account"]
    container_name = azure_config["container"]
    account_url = f"https://{account_name}.dfs.core.windows.net"
    credential = AzureCliCredential()
    service_client = DataLakeServiceClient(account_url=account_url, credential=credential)
    return service_client.get_file_system_client(container_name)


def ensure_adls_directory(file_system_client, directory_path: str) -> None:
    current = ""
    for part in directory_path.strip("/").split("/"):
        current = part if not current else f"{current}/{part}"
        directory_client = file_system_client.get_directory_client(current)
        try:
            directory_client.create_directory()
        except ResourceExistsError:
            pass


def read_adls_parquet(file_system_client, file_path: str) -> pd.DataFrame:
    file_client = file_system_client.get_file_client(file_path)
    data = file_client.download_file().readall()
    return pd.read_parquet(io.BytesIO(data))


def write_adls_parquet(file_system_client, df: pd.DataFrame, file_path: str) -> int:
    ensure_adls_directory(file_system_client, os.path.dirname(file_path))
    buffer = io.BytesIO()
    df.to_parquet(buffer, index=False, engine="pyarrow")
    buffer.seek(0)
    file_system_client.get_file_client(file_path).upload_data(buffer.getvalue(), overwrite=True)
    written_df = read_adls_parquet(file_system_client, file_path)
    return len(written_df)


def upload_log_to_adls(file_system_client, local_log_file: str, remote_log_file: str) -> None:
    if not os.path.exists(local_log_file):
        return
    ensure_adls_directory(file_system_client, os.path.dirname(remote_log_file))
    with open(local_log_file, "rb") as f:
        file_system_client.get_file_client(remote_log_file).upload_data(f.read(), overwrite=True)


def read_latest_bronze(bronze_path: str, table_name: str) -> pd.DataFrame:
    """Read the most recent ingestion_date partition for a table."""
    table_dir = os.path.join(bronze_path, table_name)
    partitions = sorted(
        [d for d in os.listdir(table_dir) if d.startswith("ingestion_date=")],
        reverse=True,
    )
    if not partitions:
        raise FileNotFoundError(f"No Bronze partitions found for {table_name}")
    latest = os.path.join(table_dir, partitions[0])
    files = [os.path.join(latest, f) for f in os.listdir(latest) if f.endswith(".parquet")]
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)


def read_latest_bronze_azure(
    file_system_client, bronze_prefix: str, table_name: str
) -> pd.DataFrame:
    """Read the most recent ingestion_date partition for a table from ADLS."""
    table_dir = f"{bronze_prefix.strip('/')}/{table_name}"
    partitions = set()
    for path in file_system_client.get_paths(path=table_dir):
        relative = path.name.replace(f"{table_dir}/", "", 1)
        partition = relative.split("/", 1)[0]
        if partition.startswith("ingestion_date="):
            partitions.add(partition)

    if not partitions:
        raise FileNotFoundError(f"No ADLS Bronze partitions found for {table_name}")

    latest_dir = f"{table_dir}/{sorted(partitions, reverse=True)[0]}"
    files = [
        path.name
        for path in file_system_client.get_paths(path=latest_dir)
        if path.name.endswith(".parquet")
    ]
    if not files:
        raise FileNotFoundError(f"No ADLS Bronze Parquet files found for {table_name}")

    return pd.concat([read_adls_parquet(file_system_client, f) for f in files], ignore_index=True)


def drop_bronze_metadata(df: pd.DataFrame) -> pd.DataFrame:
    """Remove Bronze metadata columns before Silver processing."""
    meta_cols = ["ingestion_timestamp", "source_file_name", "batch_id", "ingestion_date"]
    return df.drop(columns=[c for c in meta_cols if c in df.columns])


def write_silver(df: pd.DataFrame, silver_path: str, table_name: str):
    out_dir = os.path.join(silver_path, table_name)
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, f"{table_name}_clean.parquet")
    df.to_parquet(out_file, index=False, engine="pyarrow")
    logger.success(f"[{table_name}] ✅ Silver → {out_file} ({len(df):,} rows)")


def write_silver_azure(df: pd.DataFrame, file_system_client, silver_prefix: str, table_name: str):
    out_file = f"{silver_prefix.strip('/')}/{table_name}/{table_name}_clean.parquet"
    written_rows = write_adls_parquet(file_system_client, df, out_file)
    logger.success(f"[{table_name}] Silver -> ADLS {out_file} ({written_rows:,} rows)")


def write_rejected(df: pd.DataFrame, rejected_path: str, table_name: str):
    if df.empty:
        return
    out_dir = os.path.join(rejected_path, table_name)
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, f"rejected_{table_name}.parquet")
    df["rejection_timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df.to_parquet(out_file, index=False, engine="pyarrow")
    logger.warning(f"[{table_name}] ⚠️  Rejected {len(df):,} rows → {out_file}")


def write_rejected_azure(
    df: pd.DataFrame, file_system_client, rejected_prefix: str, table_name: str
):
    if df.empty:
        return
    rejected_df = df.copy()
    rejected_df["rejection_timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    out_file = f"{rejected_prefix.strip('/')}/{table_name}/rejected_{table_name}.parquet"
    written_rows = write_adls_parquet(file_system_client, rejected_df, out_file)
    logger.warning(f"[{table_name}] Rejected {written_rows:,} rows -> ADLS {out_file}")


def apply_dq_rule(df, log_path, table_name, rule_id, rule_desc, mask):
    """
    Apply a boolean mask (True = PASS). Log result. Return (good_df, bad_df).
    """
    passed = df[mask].copy()
    failed = df[~mask].copy()
    failed["dq_failure_reason"] = rule_desc
    failed["dq_rule_id"] = rule_id
    write_dq_log(
        log_path,
        table_name,
        rule_id,
        rule_desc,
        len(df),
        len(passed),
        len(failed),
    )
    if len(failed) > 0:
        logger.warning(f"[{table_name}] {rule_id}: {len(failed):,} failed — {rule_desc}")
    return passed, failed


def safe_to_datetime(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


# ─────────────────────────────────────────────
# Per-table cleaning functions
# ─────────────────────────────────────────────


def clean_customers(df, log_path):
    table = "customers"
    df = drop_bronze_metadata(df)
    df = df.drop_duplicates()

    # Standardize strings
    for col in ["customer_city", "customer_state"]:
        if col in df.columns:
            df[col] = df[col].str.strip().str.lower()
    df["customer_state"] = df["customer_state"].str.upper()
    df["customer_zip_code_prefix"] = df["customer_zip_code_prefix"].astype(str).str.zfill(5)

    rejected_frames = []

    # DQ-CUST-001: customer_id not null
    df, rej = apply_dq_rule(
        df,
        log_path,
        table,
        "DQ-CUST-001",
        "customer_id must not be null",
        df["customer_id"].notna(),
    )
    rejected_frames.append(rej)

    # DQ-CUST-002: customer_unique_id not null
    df, rej = apply_dq_rule(
        df,
        log_path,
        table,
        "DQ-CUST-002",
        "customer_unique_id must not be null",
        df["customer_unique_id"].notna(),
    )
    rejected_frames.append(rej)

    # DQ-CUST-003: valid state code
    df, rej = apply_dq_rule(
        df,
        log_path,
        table,
        "DQ-CUST-003",
        "customer_state must be a valid Brazilian state code",
        df["customer_state"].isin(VALID_STATES) | df["customer_state"].isna(),
    )
    rejected_frames.append(rej)

    rejected = pd.concat(rejected_frames, ignore_index=True)
    return df, rejected


def clean_orders(df, log_path, customers_df=None):
    table = "orders"
    df = drop_bronze_metadata(df)
    df = df.drop_duplicates(subset=["order_id"])

    # Cast timestamps
    for col in [
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ]:
        if col in df.columns:
            df[col] = safe_to_datetime(df[col])

    df["order_status"] = df["order_status"].str.strip().str.lower()

    rejected_frames = []

    # DQ-ORD-001
    df, rej = apply_dq_rule(
        df, log_path, table, "DQ-ORD-001", "order_id must not be null", df["order_id"].notna()
    )
    rejected_frames.append(rej)

    # DQ-ORD-002
    df, rej = apply_dq_rule(
        df, log_path, table, "DQ-ORD-002", "customer_id must not be null", df["customer_id"].notna()
    )
    rejected_frames.append(rej)

    # DQ-ORD-003
    df, rej = apply_dq_rule(
        df,
        log_path,
        table,
        "DQ-ORD-003",
        "order_status must be a known value",
        df["order_status"].isin(VALID_ORDER_STATUSES),
    )
    rejected_frames.append(rej)

    # DQ-ORD-004
    df, rej = apply_dq_rule(
        df,
        log_path,
        table,
        "DQ-ORD-004",
        "order_purchase_timestamp must not be null",
        df["order_purchase_timestamp"].notna(),
    )
    rejected_frames.append(rej)

    # DQ-ORD-005: delivered date >= purchase date
    has_delivery = df["order_delivered_customer_date"].notna()
    valid_dates = ~has_delivery | (
        df["order_delivered_customer_date"] >= df["order_purchase_timestamp"]
    )
    df, rej = apply_dq_rule(
        df, log_path, table, "DQ-ORD-005", "delivered date must be >= purchase date", valid_dates
    )
    rejected_frames.append(rej)

    rejected = pd.concat(rejected_frames, ignore_index=True)
    return df, rejected


def clean_order_items(df, log_path, orders_df=None, products_df=None, sellers_df=None):
    table = "order_items"
    df = drop_bronze_metadata(df)
    df = df.drop_duplicates()

    df["order_item_id"] = pd.to_numeric(df["order_item_id"], errors="coerce").astype("Int64")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["freight_value"] = pd.to_numeric(df["freight_value"], errors="coerce")
    df["shipping_limit_date"] = safe_to_datetime(df["shipping_limit_date"])

    rejected_frames = []

    df, rej = apply_dq_rule(
        df, log_path, table, "DQ-ITM-001", "order_id must not be null", df["order_id"].notna()
    )
    rejected_frames.append(rej)

    df, rej = apply_dq_rule(
        df, log_path, table, "DQ-ITM-002", "product_id must not be null", df["product_id"].notna()
    )
    rejected_frames.append(rej)

    df, rej = apply_dq_rule(
        df, log_path, table, "DQ-ITM-003", "seller_id must not be null", df["seller_id"].notna()
    )
    rejected_frames.append(rej)

    df, rej = apply_dq_rule(
        df, log_path, table, "DQ-ITM-004", "price must be >= 0", df["price"].fillna(0) >= 0
    )
    rejected_frames.append(rej)

    df, rej = apply_dq_rule(
        df,
        log_path,
        table,
        "DQ-ITM-005",
        "freight_value must be >= 0",
        df["freight_value"].fillna(0) >= 0,
    )
    rejected_frames.append(rej)

    rejected = pd.concat(rejected_frames, ignore_index=True)
    return df, rejected


def clean_products(df, log_path):
    table = "products"
    df = drop_bronze_metadata(df)
    df = df.drop_duplicates(subset=["product_id"])

    numeric_cols = [
        "product_name_lenght",
        "product_description_lenght",
        "product_photos_qty",
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "product_category_name" in df.columns:
        df["product_category_name"] = df["product_category_name"].str.strip().str.lower()

    rejected_frames = []

    df, rej = apply_dq_rule(
        df, log_path, table, "DQ-PRD-001", "product_id must not be null", df["product_id"].notna()
    )
    rejected_frames.append(rej)

    df, rej = apply_dq_rule(
        df,
        log_path,
        table,
        "DQ-PRD-002",
        "product_weight_g must be > 0 if present",
        df["product_weight_g"].isna() | (df["product_weight_g"] > 0),
    )
    rejected_frames.append(rej)

    rejected = pd.concat(rejected_frames, ignore_index=True)
    return df, rejected


def clean_sellers(df, log_path):
    table = "sellers"
    df = drop_bronze_metadata(df)
    df = df.drop_duplicates(subset=["seller_id"])

    for col in ["seller_city", "seller_state"]:
        if col in df.columns:
            df[col] = df[col].str.strip().str.lower()
    df["seller_state"] = df["seller_state"].str.upper()
    df["seller_zip_code_prefix"] = df["seller_zip_code_prefix"].astype(str).str.zfill(5)

    rejected_frames = []

    df, rej = apply_dq_rule(
        df, log_path, table, "DQ-SEL-001", "seller_id must not be null", df["seller_id"].notna()
    )
    rejected_frames.append(rej)

    rejected = pd.concat(rejected_frames, ignore_index=True)
    return df, rejected


def clean_payments(df, log_path):
    table = "payments"
    df = drop_bronze_metadata(df)
    df = df.drop_duplicates()

    df["payment_value"] = pd.to_numeric(df["payment_value"], errors="coerce")
    df["payment_installments"] = pd.to_numeric(df["payment_installments"], errors="coerce").astype(
        "Int64"
    )
    df["payment_sequential"] = pd.to_numeric(df["payment_sequential"], errors="coerce").astype(
        "Int64"
    )
    df["payment_type"] = df["payment_type"].str.strip().str.lower()

    rejected_frames = []

    df, rej = apply_dq_rule(
        df, log_path, table, "DQ-PAY-001", "order_id must not be null", df["order_id"].notna()
    )
    rejected_frames.append(rej)

    df, rej = apply_dq_rule(
        df,
        log_path,
        table,
        "DQ-PAY-002",
        "payment_value must be >= 0",
        df["payment_value"].fillna(0) >= 0,
    )
    rejected_frames.append(rej)

    df, rej = apply_dq_rule(
        df,
        log_path,
        table,
        "DQ-PAY-003",
        "payment_installments must be >= 1",
        df["payment_installments"].fillna(1) >= 1,
    )
    rejected_frames.append(rej)

    df, rej = apply_dq_rule(
        df,
        log_path,
        table,
        "DQ-PAY-004",
        "payment_type must be a known value",
        df["payment_type"].isin(VALID_PAYMENT_TYPES),
    )
    rejected_frames.append(rej)

    rejected = pd.concat(rejected_frames, ignore_index=True)
    return df, rejected


def clean_reviews(df, log_path):
    table = "reviews"
    df = drop_bronze_metadata(df)
    df = df.drop_duplicates(subset=["review_id"])

    df["review_score"] = pd.to_numeric(df["review_score"], errors="coerce").astype("Int64")
    for col in ["review_creation_date", "review_answer_timestamp"]:
        if col in df.columns:
            df[col] = safe_to_datetime(df[col])
    for col in ["review_comment_title", "review_comment_message"]:
        if col in df.columns:
            df[col] = df[col].str.strip()

    rejected_frames = []

    df, rej = apply_dq_rule(
        df, log_path, table, "DQ-REV-001", "review_id must not be null", df["review_id"].notna()
    )
    rejected_frames.append(rej)

    df, rej = apply_dq_rule(
        df, log_path, table, "DQ-REV-002", "order_id must not be null", df["order_id"].notna()
    )
    rejected_frames.append(rej)

    df, rej = apply_dq_rule(
        df,
        log_path,
        table,
        "DQ-REV-003",
        "review_score must be between 1 and 5",
        df["review_score"].between(1, 5),
    )
    rejected_frames.append(rej)

    rejected = pd.concat(rejected_frames, ignore_index=True)
    return df, rejected


def clean_geolocation(df, log_path):
    table = "geolocation"
    df = drop_bronze_metadata(df)

    df["geolocation_lat"] = pd.to_numeric(df["geolocation_lat"], errors="coerce")
    df["geolocation_lng"] = pd.to_numeric(df["geolocation_lng"], errors="coerce")
    df["geolocation_state"] = df["geolocation_state"].str.strip().str.upper()
    df["geolocation_city"] = df["geolocation_city"].str.strip().str.lower()
    df["geolocation_zip_code_prefix"] = df["geolocation_zip_code_prefix"].astype(str).str.zfill(5)

    # Drop duplicates — keep one geo point per ZIP prefix
    df = df.drop_duplicates(subset=["geolocation_zip_code_prefix"])

    # Log a single pass rule
    write_dq_log(
        log_path,
        table,
        "DQ-GEO-001",
        "geolocation_zip_code_prefix deduplication",
        len(df),
        len(df),
        0,
    )

    return df, pd.DataFrame()


def clean_product_category_translation(df, log_path):
    table = "product_category_translation"
    df = drop_bronze_metadata(df)
    df = df.drop_duplicates()
    df["product_category_name"] = df["product_category_name"].str.strip().str.lower()
    df["product_category_name_english"] = (
        df["product_category_name_english"].str.strip().str.lower()
    )

    write_dq_log(log_path, table, "DQ-CAT-001", "All records valid", len(df), len(df), 0)

    return df, pd.DataFrame()


# ─────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────

CLEANERS = {
    "customers": clean_customers,
    "orders": clean_orders,
    "order_items": clean_order_items,
    "products": clean_products,
    "sellers": clean_sellers,
    "payments": clean_payments,
    "reviews": clean_reviews,
    "geolocation": clean_geolocation,
    "product_category_translation": clean_product_category_translation,
}


def run_silver_transformations(environment: str = "local"):
    setup_logger()

    logger.info("=" * 60)
    logger.info(f"  Silver Transformation Pipeline - Starting ({environment})")
    logger.info("=" * 60)

    config = load_config()
    bronze_path = config["paths"]["local"]["bronze"]
    silver_path = config["paths"]["local"]["silver"]
    rejected_path = config["paths"]["local"]["rejected"]
    log_path = config["paths"]["local"]["logs"]
    azure_config = config["paths"]["azure"]

    if environment not in ["local", "azure"]:
        raise ValueError("environment must be either 'local' or 'azure'")

    os.makedirs(log_path, exist_ok=True)

    # Clear previous DQ report for fresh run
    dq_report_file = os.path.join(log_path, "data_quality_report.csv")
    if os.path.exists(dq_report_file):
        os.remove(dq_report_file)

    file_system_client = None
    if environment == "azure":
        file_system_client = get_adls_file_system_client(azure_config)
        logger.info(
            "ADLS target    : "
            f"abfss://{azure_config['container']}@"
            f"{azure_config['storage_account']}.dfs.core.windows.net/"
        )

    results = []
    for table_name, cleaner_fn in CLEANERS.items():
        logger.info(f"[{table_name}] Processing...")
        try:
            if environment == "azure":
                raw_df = read_latest_bronze_azure(
                    file_system_client, azure_config["bronze_prefix"], table_name
                )
            else:
                raw_df = read_latest_bronze(bronze_path, table_name)
            logger.info(f"[{table_name}] Loaded {len(raw_df):,} Bronze rows")

            clean_df, rejected_df = cleaner_fn(raw_df, log_path)

            if environment == "azure":
                write_silver_azure(
                    clean_df, file_system_client, azure_config["silver_prefix"], table_name
                )
                write_rejected_azure(
                    rejected_df, file_system_client, azure_config["rejected_prefix"], table_name
                )
            else:
                write_silver(clean_df, silver_path, table_name)
                write_rejected(rejected_df, rejected_path, table_name)

            results.append(
                {
                    "table": table_name,
                    "bronze_rows": len(raw_df),
                    "silver_rows": len(clean_df),
                    "rejected_rows": len(rejected_df),
                    "status": "SUCCESS",
                }
            )

        except Exception as e:
            logger.error(f"[{table_name}] FAILED: {e}")
            results.append(
                {
                    "table": table_name,
                    "bronze_rows": 0,
                    "silver_rows": 0,
                    "rejected_rows": 0,
                    "status": f"FAILED: {e}",
                }
            )

    # ── Summary ─────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("  Silver Transformation Summary")
    logger.info("=" * 60)
    logger.info(f"{'Table':<35} {'Bronze':>8} {'Silver':>8} {'Rejected':>9} {'Status'}")
    logger.info("-" * 70)
    for r in results:
        logger.info(
            f"{r['table']:<35} {r['bronze_rows']:>8,} {r['silver_rows']:>8,} "
            f"{r['rejected_rows']:>9,}  {r['status']}"
        )
    total_silver = sum(r["silver_rows"] for r in results)
    total_rejected = sum(r["rejected_rows"] for r in results)
    logger.info("-" * 70)
    logger.info(f"{'TOTAL':<35} {'':>8} {total_silver:>8,} {total_rejected:>9,}")
    logger.info(f"DQ report -> {dq_report_file}")

    if environment == "azure" and file_system_client is not None:
        remote_log_file = f"{azure_config['logs_prefix'].strip('/')}/data_quality_report.csv"
        upload_log_to_adls(file_system_client, dq_report_file, remote_log_file)
        logger.info(f"DQ report uploaded to ADLS: {remote_log_file}")

    logger.info("=" * 60)
    logger.info("  Silver Transformation Pipeline - Complete")
    logger.info("=" * 60)

    failed = [r for r in results if not r["status"].startswith("SUCCESS")]
    if failed:
        failed_tables = ", ".join(r["table"] for r in failed)
        raise RuntimeError(f"Silver transformation failed for: {failed_tables}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Silver transformation pipeline.")
    parser.add_argument(
        "--environment",
        choices=["local", "azure"],
        default="local",
        help="Run against local filesystem or Azure Data Lake Storage Gen2.",
    )
    args = parser.parse_args()
    run_silver_transformations(environment=args.environment)
