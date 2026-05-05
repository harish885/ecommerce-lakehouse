"""
Bronze Layer Ingestion Pipeline
================================
Reads raw CSV files from data/raw/, adds metadata columns,
and writes Parquet files to data/bronze/{table}/ingestion_date=YYYY-MM-DD/.

Usage:
    python src/ingestion/bronze_ingestion.py

Output:
    data/bronze/{table}/ingestion_date=YYYY-MM-DD/{table}_{batch_id}.parquet
    logs/bronze_ingestion_log.csv
"""

import os
import sys
import uuid
from datetime import datetime, date

import pandas as pd
import yaml
from loguru import logger

# Allow imports from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from src.utils.logger import setup_logger, write_ingestion_log


# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────

def load_config(config_path: str = "config/config.yaml") -> dict:
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


# ─────────────────────────────────────────────
# Core ingestion function
# ─────────────────────────────────────────────

def ingest_table(
    table_config: dict,
    raw_path: str,
    bronze_path: str,
    log_path: str,
    batch_id: str,
    ingestion_date: str,
) -> dict:
    """
    Ingest one CSV table from raw zone to bronze layer.

    Returns a summary dict with status, rows, and any error.
    """
    table_name = table_config["name"]
    source_file = table_config["source_file"]
    source_path = os.path.join(raw_path, source_file)

    summary = {
        "table": table_name,
        "source_file": source_file,
        "rows_ingested": 0,
        "status": "FAILED",
        "error": "",
    }

    # ── 1. File existence check ──────────────────────────────
    if not os.path.isfile(source_path):
        msg = f"Source file not found: {source_path}"
        logger.error(f"[{table_name}] {msg}")
        summary["error"] = msg
        write_ingestion_log(log_path, table_name, source_file, 0, "FAILED", msg, batch_id)
        return summary

    # ── 2. Read CSV ──────────────────────────────────────────
    try:
        df = pd.read_csv(source_path, low_memory=False)
    except Exception as e:
        msg = f"Failed to read CSV: {e}"
        logger.error(f"[{table_name}] {msg}")
        summary["error"] = msg
        write_ingestion_log(log_path, table_name, source_file, 0, "FAILED", msg, batch_id)
        return summary

    # ── 3. Empty file check ──────────────────────────────────
    if df.empty:
        msg = "CSV file is empty (zero rows)"
        logger.warning(f"[{table_name}] {msg}")
        summary["status"] = "SKIPPED"
        summary["error"] = msg
        write_ingestion_log(log_path, table_name, source_file, 0, "SKIPPED", msg, batch_id)
        return summary

    raw_row_count = len(df)
    logger.info(f"[{table_name}] Read {raw_row_count:,} rows from {source_file}")

    # ── 4. Add metadata columns ──────────────────────────────
    ingestion_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df["ingestion_timestamp"] = ingestion_ts
    df["source_file_name"] = source_file
    df["batch_id"] = batch_id
    df["ingestion_date"] = ingestion_date

    # ── 5. Build output path (Hive-style partition) ──────────
    output_dir = os.path.join(bronze_path, table_name, f"ingestion_date={ingestion_date}")
    os.makedirs(output_dir, exist_ok=True)

    output_file = os.path.join(output_dir, f"{table_name}_{batch_id}.parquet")

    # ── 6. Write Parquet ─────────────────────────────────────
    try:
        df.to_parquet(output_file, index=False, engine="pyarrow")
    except Exception as e:
        msg = f"Failed to write Parquet: {e}"
        logger.error(f"[{table_name}] {msg}")
        summary["error"] = msg
        write_ingestion_log(log_path, table_name, source_file, 0, "FAILED", msg, batch_id)
        return summary

    # ── 7. Verify written file ───────────────────────────────
    written_df = pd.read_parquet(output_file)
    written_rows = len(written_df)

    logger.success(
        f"[{table_name}] ✅ Ingested {written_rows:,} rows → {output_file}"
    )

    # ── 8. Log result ────────────────────────────────────────
    summary.update({"rows_ingested": written_rows, "status": "SUCCESS", "error": ""})
    write_ingestion_log(
        log_path, table_name, source_file, written_rows, "SUCCESS", "", batch_id
    )

    return summary


# ─────────────────────────────────────────────
# Main pipeline runner
# ─────────────────────────────────────────────

def run_bronze_ingestion():
    setup_logger()

    logger.info("=" * 60)
    logger.info("  Bronze Ingestion Pipeline — Starting")
    logger.info("=" * 60)

    # Load config
    config = load_config()
    raw_path = config["paths"]["local"]["raw"]
    bronze_path = config["paths"]["local"]["bronze"]
    log_path = config["paths"]["local"]["logs"]
    tables = config["tables"]

    # Generate batch identifiers
    ingestion_date = date.today().strftime("%Y-%m-%d")
    batch_id = f"batch_{date.today().strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}"

    logger.info(f"Ingestion date : {ingestion_date}")
    logger.info(f"Batch ID       : {batch_id}")
    logger.info(f"Tables to ingest: {len(tables)}")
    logger.info("-" * 60)

    results = []
    for table_config in tables:
        result = ingest_table(
            table_config=table_config,
            raw_path=raw_path,
            bronze_path=bronze_path,
            log_path=log_path,
            batch_id=batch_id,
            ingestion_date=ingestion_date,
        )
        results.append(result)

    # ── Print summary ────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("  Bronze Ingestion Summary")
    logger.info("=" * 60)

    succeeded = [r for r in results if r["status"] == "SUCCESS"]
    failed = [r for r in results if r["status"] == "FAILED"]
    skipped = [r for r in results if r["status"] == "SKIPPED"]

    total_rows = sum(r["rows_ingested"] for r in succeeded)

    logger.info(f"✅ Success : {len(succeeded)} tables")
    logger.info(f"⚠️  Skipped : {len(skipped)} tables")
    logger.info(f"❌ Failed  : {len(failed)} tables")
    logger.info(f"📦 Total rows ingested: {total_rows:,}")
    logger.info(f"📋 Log written to: {log_path}/bronze_ingestion_log.csv")

    if failed:
        logger.warning("Failed tables:")
        for r in failed:
            logger.warning(f"  - {r['table']}: {r['error']}")

    logger.info("=" * 60)
    logger.info("  Bronze Ingestion Pipeline — Complete")
    logger.info("=" * 60)

    return results


if __name__ == "__main__":
    run_bronze_ingestion()
