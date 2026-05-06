"""
Silver Layer Transformation Pipeline
======================================
Reads the latest Bronze partition for each table, applies cleaning,
deduplication, type casting, and data quality checks. Records that pass
every rule land in the Silver layer; records that fail any rule land in
the Rejected zone with a `dq_failure_reason` column.

Runs identically against local filesystem and Azure Data Lake Storage Gen2
via the `Storage` abstraction.

Usage
-----
    python -m src.transformation.silver_transformations
    python -m src.transformation.silver_transformations --environment azure

Outputs
-------
    {silver_root}/{table}/{table}_clean.parquet
    {rejected_root}/{table}/rejected_{table}.parquet
    {logs_root}/data_quality_report.csv
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable

import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.utils.config import load_config
from src.utils.logger import setup_logger, write_dq_log
from src.utils.storage import (
    AdlsStorage,
    LayerPaths,
    Storage,
    get_storage,
)


# ─────────────────────────────────────────────
# Reference data (validation lookups)
# ─────────────────────────────────────────────

# All 27 Brazilian state codes (26 states + Federal District).
VALID_STATES: frozenset[str] = frozenset(
    [
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
)

VALID_ORDER_STATUSES: frozenset[str] = frozenset(
    [
        "delivered",
        "shipped",
        "canceled",
        "unavailable",
        "processing",
        "invoiced",
        "approved",
        "created",
    ]
)

VALID_PAYMENT_TYPES: frozenset[str] = frozenset(
    ["credit_card", "boleto", "voucher", "debit_card", "not_defined"]
)

# Bronze metadata columns added during ingestion. Always stripped before
# Silver processing — Silver and Gold are concerned with business data only.
_BRONZE_METADATA = ("ingestion_timestamp", "source_file_name", "batch_id", "ingestion_date")


# ─────────────────────────────────────────────
# Pure helpers (no I/O — easy to unit test)
# ─────────────────────────────────────────────


def drop_bronze_metadata(df: pd.DataFrame) -> pd.DataFrame:
    """Remove the four Bronze audit columns if present."""
    return df.drop(columns=[c for c in _BRONZE_METADATA if c in df.columns])


def _strip_lower(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Strip whitespace and lowercase the given string columns in-place."""
    for col in cols:
        if col in df.columns:
            df[col] = df[col].str.strip().str.lower()
    return df


def _zip_5digit(series: pd.Series) -> pd.Series:
    """Cast a ZIP prefix to a zero-padded 5-character string."""
    return series.astype(str).str.zfill(5)


def _safe_to_datetime(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def _apply_dq_rule(
    df: pd.DataFrame,
    log_path: str,
    table: str,
    rule_id: str,
    rule_desc: str,
    mask: pd.Series,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split `df` into (passed, failed) rows according to a boolean `mask`.
    Failed rows get `dq_failure_reason` and `dq_rule_id` columns.
    A row is also written to the data-quality CSV log.
    """
    passed = df[mask].copy()
    failed = df[~mask].copy()
    failed["dq_failure_reason"] = rule_desc
    failed["dq_rule_id"] = rule_id

    write_dq_log(log_path, table, rule_id, rule_desc, len(df), len(passed), len(failed))
    if len(failed) > 0:
        logger.warning(f"[{table}] {rule_id}: {len(failed):,} failed — {rule_desc}")
    return passed, failed


def _concat_rejected(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Combine all rejected slices into one frame, dropping empty entries."""
    non_empty = [f for f in frames if not f.empty]
    if not non_empty:
        return pd.DataFrame()
    return pd.concat(non_empty, ignore_index=True)


# ─────────────────────────────────────────────
# Per-table cleaning functions
#
# Signature: clean_<table>(df, log_path) -> (clean_df, rejected_df)
#
# These are deliberately importable as plain functions so unit tests can
# call them on small in-memory DataFrames without any I/O.
# ─────────────────────────────────────────────


def clean_customers(df: pd.DataFrame, log_path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    table = "customers"
    df = drop_bronze_metadata(df).drop_duplicates()

    df = _strip_lower(df, ["customer_city", "customer_state"])
    df["customer_state"] = df["customer_state"].str.upper()
    df["customer_zip_code_prefix"] = _zip_5digit(df["customer_zip_code_prefix"])

    rejected: list[pd.DataFrame] = []
    df, rej = _apply_dq_rule(
        df,
        log_path,
        table,
        "DQ-CUST-001",
        "customer_id must not be null",
        df["customer_id"].notna(),
    )
    rejected.append(rej)
    df, rej = _apply_dq_rule(
        df,
        log_path,
        table,
        "DQ-CUST-002",
        "customer_unique_id must not be null",
        df["customer_unique_id"].notna(),
    )
    rejected.append(rej)
    df, rej = _apply_dq_rule(
        df,
        log_path,
        table,
        "DQ-CUST-003",
        "customer_state must be a valid Brazilian state code",
        df["customer_state"].isin(VALID_STATES) | df["customer_state"].isna(),
    )
    rejected.append(rej)
    return df, _concat_rejected(rejected)


def clean_orders(df: pd.DataFrame, log_path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    table = "orders"
    df = drop_bronze_metadata(df).drop_duplicates(subset=["order_id"])

    timestamp_cols = [
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ]
    for col in timestamp_cols:
        if col in df.columns:
            df[col] = _safe_to_datetime(df[col])

    df["order_status"] = df["order_status"].str.strip().str.lower()

    rejected: list[pd.DataFrame] = []
    df, rej = _apply_dq_rule(
        df,
        log_path,
        table,
        "DQ-ORD-001",
        "order_id must not be null",
        df["order_id"].notna(),
    )
    rejected.append(rej)
    df, rej = _apply_dq_rule(
        df,
        log_path,
        table,
        "DQ-ORD-002",
        "customer_id must not be null",
        df["customer_id"].notna(),
    )
    rejected.append(rej)
    df, rej = _apply_dq_rule(
        df,
        log_path,
        table,
        "DQ-ORD-003",
        "order_status must be a known value",
        df["order_status"].isin(VALID_ORDER_STATUSES),
    )
    rejected.append(rej)
    df, rej = _apply_dq_rule(
        df,
        log_path,
        table,
        "DQ-ORD-004",
        "order_purchase_timestamp must not be null",
        df["order_purchase_timestamp"].notna(),
    )
    rejected.append(rej)

    has_delivery = df["order_delivered_customer_date"].notna()
    delivery_after_purchase = ~has_delivery | (
        df["order_delivered_customer_date"] >= df["order_purchase_timestamp"]
    )
    df, rej = _apply_dq_rule(
        df,
        log_path,
        table,
        "DQ-ORD-005",
        "delivered date must be >= purchase date",
        delivery_after_purchase,
    )
    rejected.append(rej)
    return df, _concat_rejected(rejected)


def clean_order_items(df: pd.DataFrame, log_path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    table = "order_items"
    df = drop_bronze_metadata(df).drop_duplicates()

    df["order_item_id"] = pd.to_numeric(df["order_item_id"], errors="coerce").astype("Int64")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["freight_value"] = pd.to_numeric(df["freight_value"], errors="coerce")
    df["shipping_limit_date"] = _safe_to_datetime(df["shipping_limit_date"])

    rejected: list[pd.DataFrame] = []
    df, rej = _apply_dq_rule(
        df,
        log_path,
        table,
        "DQ-ITM-001",
        "order_id must not be null",
        df["order_id"].notna(),
    )
    rejected.append(rej)
    df, rej = _apply_dq_rule(
        df,
        log_path,
        table,
        "DQ-ITM-002",
        "product_id must not be null",
        df["product_id"].notna(),
    )
    rejected.append(rej)
    df, rej = _apply_dq_rule(
        df,
        log_path,
        table,
        "DQ-ITM-003",
        "seller_id must not be null",
        df["seller_id"].notna(),
    )
    rejected.append(rej)
    df, rej = _apply_dq_rule(
        df,
        log_path,
        table,
        "DQ-ITM-004",
        "price must be >= 0",
        df["price"].fillna(0) >= 0,
    )
    rejected.append(rej)
    df, rej = _apply_dq_rule(
        df,
        log_path,
        table,
        "DQ-ITM-005",
        "freight_value must be >= 0",
        df["freight_value"].fillna(0) >= 0,
    )
    rejected.append(rej)
    return df, _concat_rejected(rejected)


def clean_products(df: pd.DataFrame, log_path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    table = "products"
    df = drop_bronze_metadata(df).drop_duplicates(subset=["product_id"])

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

    rejected: list[pd.DataFrame] = []
    df, rej = _apply_dq_rule(
        df,
        log_path,
        table,
        "DQ-PRD-001",
        "product_id must not be null",
        df["product_id"].notna(),
    )
    rejected.append(rej)
    df, rej = _apply_dq_rule(
        df,
        log_path,
        table,
        "DQ-PRD-002",
        "product_weight_g must be > 0 if present",
        df["product_weight_g"].isna() | (df["product_weight_g"] > 0),
    )
    rejected.append(rej)
    return df, _concat_rejected(rejected)


def clean_sellers(df: pd.DataFrame, log_path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    table = "sellers"
    df = drop_bronze_metadata(df).drop_duplicates(subset=["seller_id"])

    df = _strip_lower(df, ["seller_city", "seller_state"])
    df["seller_state"] = df["seller_state"].str.upper()
    df["seller_zip_code_prefix"] = _zip_5digit(df["seller_zip_code_prefix"])

    rejected: list[pd.DataFrame] = []
    df, rej = _apply_dq_rule(
        df,
        log_path,
        table,
        "DQ-SEL-001",
        "seller_id must not be null",
        df["seller_id"].notna(),
    )
    rejected.append(rej)
    return df, _concat_rejected(rejected)


def clean_payments(df: pd.DataFrame, log_path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    table = "payments"
    df = drop_bronze_metadata(df).drop_duplicates()

    df["payment_value"] = pd.to_numeric(df["payment_value"], errors="coerce")
    df["payment_installments"] = pd.to_numeric(df["payment_installments"], errors="coerce").astype(
        "Int64"
    )
    df["payment_sequential"] = pd.to_numeric(df["payment_sequential"], errors="coerce").astype(
        "Int64"
    )
    df["payment_type"] = df["payment_type"].str.strip().str.lower()

    rejected: list[pd.DataFrame] = []
    df, rej = _apply_dq_rule(
        df,
        log_path,
        table,
        "DQ-PAY-001",
        "order_id must not be null",
        df["order_id"].notna(),
    )
    rejected.append(rej)
    df, rej = _apply_dq_rule(
        df,
        log_path,
        table,
        "DQ-PAY-002",
        "payment_value must be >= 0",
        df["payment_value"].fillna(0) >= 0,
    )
    rejected.append(rej)
    df, rej = _apply_dq_rule(
        df,
        log_path,
        table,
        "DQ-PAY-003",
        "payment_installments must be >= 1",
        df["payment_installments"].fillna(1) >= 1,
    )
    rejected.append(rej)
    df, rej = _apply_dq_rule(
        df,
        log_path,
        table,
        "DQ-PAY-004",
        "payment_type must be a known value",
        df["payment_type"].isin(VALID_PAYMENT_TYPES),
    )
    rejected.append(rej)
    return df, _concat_rejected(rejected)


def clean_reviews(df: pd.DataFrame, log_path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    table = "reviews"
    df = drop_bronze_metadata(df).drop_duplicates(subset=["review_id"])

    df["review_score"] = pd.to_numeric(df["review_score"], errors="coerce").astype("Int64")
    for col in ["review_creation_date", "review_answer_timestamp"]:
        if col in df.columns:
            df[col] = _safe_to_datetime(df[col])
    for col in ["review_comment_title", "review_comment_message"]:
        if col in df.columns:
            df[col] = df[col].str.strip()

    rejected: list[pd.DataFrame] = []
    df, rej = _apply_dq_rule(
        df,
        log_path,
        table,
        "DQ-REV-001",
        "review_id must not be null",
        df["review_id"].notna(),
    )
    rejected.append(rej)
    df, rej = _apply_dq_rule(
        df,
        log_path,
        table,
        "DQ-REV-002",
        "order_id must not be null",
        df["order_id"].notna(),
    )
    rejected.append(rej)
    df, rej = _apply_dq_rule(
        df,
        log_path,
        table,
        "DQ-REV-003",
        "review_score must be between 1 and 5",
        df["review_score"].between(1, 5),
    )
    rejected.append(rej)
    return df, _concat_rejected(rejected)


def clean_geolocation(df: pd.DataFrame, log_path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    table = "geolocation"
    df = drop_bronze_metadata(df)

    df["geolocation_lat"] = pd.to_numeric(df["geolocation_lat"], errors="coerce")
    df["geolocation_lng"] = pd.to_numeric(df["geolocation_lng"], errors="coerce")
    df["geolocation_state"] = df["geolocation_state"].str.strip().str.upper()
    df["geolocation_city"] = df["geolocation_city"].str.strip().str.lower()
    df["geolocation_zip_code_prefix"] = _zip_5digit(df["geolocation_zip_code_prefix"])

    # Keep one geo point per ZIP prefix.
    df = df.drop_duplicates(subset=["geolocation_zip_code_prefix"])
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


def clean_product_category_translation(
    df: pd.DataFrame, log_path: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    table = "product_category_translation"
    df = drop_bronze_metadata(df).drop_duplicates()
    df["product_category_name"] = df["product_category_name"].str.strip().str.lower()
    df["product_category_name_english"] = (
        df["product_category_name_english"].str.strip().str.lower()
    )
    write_dq_log(log_path, table, "DQ-CAT-001", "All records valid", len(df), len(df), 0)
    return df, pd.DataFrame()


# Cleaner registry — the runner iterates this in declaration order.
CleanerFn = Callable[[pd.DataFrame, str], tuple[pd.DataFrame, pd.DataFrame]]
CLEANERS: dict[str, CleanerFn] = {
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


# ─────────────────────────────────────────────
# Storage glue (Bronze → Silver / Rejected)
# ─────────────────────────────────────────────


def _read_latest_bronze(storage: Storage, bronze_root: str, table_name: str) -> pd.DataFrame:
    """Find the newest `ingestion_date=YYYY-MM-DD` partition and read all its Parquet files."""
    table_dir = f"{bronze_root.rstrip('/')}/{table_name}"
    partitions = storage.list_partitions(table_dir)
    if not partitions:
        raise FileNotFoundError(f"No Bronze partitions found for {table_name} under {table_dir}")
    latest_dir = f"{table_dir}/{partitions[0]}"
    files = storage.list_parquet_files(latest_dir)
    if not files:
        raise FileNotFoundError(f"No Parquet files in {latest_dir}")
    return storage.read_parquet_dataset(files)


def _write_silver(storage: Storage, df: pd.DataFrame, silver_root: str, table_name: str) -> None:
    out_path = f"{silver_root.rstrip('/')}/{table_name}/{table_name}_clean.parquet"
    rows = storage.write_parquet(df, out_path)
    logger.success(f"[{table_name}] Silver -> {out_path} ({rows:,} rows)")


def _write_rejected(
    storage: Storage, df: pd.DataFrame, rejected_root: str, table_name: str
) -> None:
    if df.empty:
        return
    df = df.copy()
    df["rejection_timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    out_path = f"{rejected_root.rstrip('/')}/{table_name}/rejected_{table_name}.parquet"
    rows = storage.write_parquet(df, out_path)
    logger.warning(f"[{table_name}] Rejected -> {out_path} ({rows:,} rows)")


# ─────────────────────────────────────────────
# Pipeline runner
# ─────────────────────────────────────────────


def _process_table(
    table_name: str,
    cleaner: CleanerFn,
    storage: Storage,
    paths: LayerPaths,
    log_path: str,
) -> dict:
    logger.info(f"[{table_name}] Processing...")
    try:
        bronze_df = _read_latest_bronze(storage, paths.bronze, table_name)
        logger.info(f"[{table_name}] Loaded {len(bronze_df):,} Bronze rows")
        clean_df, rejected_df = cleaner(bronze_df, log_path)
        _write_silver(storage, clean_df, paths.silver, table_name)
        _write_rejected(storage, rejected_df, paths.rejected, table_name)
        return {
            "table": table_name,
            "bronze_rows": len(bronze_df),
            "silver_rows": len(clean_df),
            "rejected_rows": len(rejected_df),
            "status": "SUCCESS",
        }
    except Exception as e:  # noqa: BLE001
        logger.error(f"[{table_name}] FAILED: {e}")
        return {
            "table": table_name,
            "bronze_rows": 0,
            "silver_rows": 0,
            "rejected_rows": 0,
            "status": f"FAILED: {e}",
        }


def run_silver_transformations(environment: str = "local") -> list[dict]:
    setup_logger()
    logger.info("=" * 60)
    logger.info(f"  Silver Transformation Pipeline - Starting ({environment})")
    logger.info("=" * 60)

    config = load_config()
    storage = get_storage(environment, config)
    paths = LayerPaths.from_config(config, environment)
    log_path = config["paths"]["local"]["logs"]
    os.makedirs(log_path, exist_ok=True)

    # Fresh DQ report on every run.
    dq_report_file = os.path.join(log_path, "data_quality_report.csv")
    if os.path.exists(dq_report_file):
        os.remove(dq_report_file)

    logger.info(f"Backend        : {storage.describe}")

    results = [
        _process_table(name, cleaner, storage, paths, log_path)
        for name, cleaner in CLEANERS.items()
    ]

    # Summary
    logger.info("=" * 60)
    logger.info("  Silver Transformation Summary")
    logger.info("=" * 60)
    logger.info(f"{'Table':<35} {'Bronze':>10} {'Silver':>10} {'Rejected':>10}  Status")
    logger.info("-" * 80)
    for r in results:
        logger.info(
            f"{r['table']:<35} {r['bronze_rows']:>10,} {r['silver_rows']:>10,} "
            f"{r['rejected_rows']:>10,}  {r['status']}"
        )
    total_silver = sum(r["silver_rows"] for r in results)
    total_rejected = sum(r["rejected_rows"] for r in results)
    logger.info("-" * 80)
    logger.info(f"{'TOTAL':<35} {'':>10} {total_silver:>10,} {total_rejected:>10,}")
    logger.info(f"DQ report -> {dq_report_file}")

    if isinstance(storage, AdlsStorage):
        remote_log_file = f"{paths.logs.rstrip('/')}/data_quality_report.csv"
        storage.upload_local_file(dq_report_file, remote_log_file)
        logger.info(f"DQ report uploaded to ADLS: {remote_log_file}")

    logger.info("=" * 60)
    logger.info("  Silver Transformation Pipeline - Complete")
    logger.info("=" * 60)

    failed = [r for r in results if not r["status"].startswith("SUCCESS")]
    if failed:
        raise RuntimeError(
            "Silver transformation failed for: " + ", ".join(r["table"] for r in failed)
        )
    return results


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Silver transformation pipeline.")
    parser.add_argument(
        "--environment",
        choices=["local", "azure"],
        default="local",
        help="Run against local filesystem or Azure Data Lake Storage Gen2.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_silver_transformations(environment=args.environment)
