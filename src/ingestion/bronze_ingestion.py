"""
Bronze Layer Ingestion Pipeline
================================
Reads raw CSV files, adds audit metadata, and writes Hive-partitioned
Parquet to the Bronze layer.

The pipeline runs identically against the local filesystem and against
Azure Data Lake Storage Gen2 — the difference is encapsulated in the
`Storage` backend selected by `--environment`.

Usage
-----
    python -m src.ingestion.bronze_ingestion
    python -m src.ingestion.bronze_ingestion --environment azure

Outputs
-------
    {bronze_root}/{table}/ingestion_date=YYYY-MM-DD/{table}_{batch_id}.parquet
    {logs_root}/bronze_ingestion_log.csv  (uploaded to ADLS in azure mode)
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from loguru import logger

# Allow `python src/ingestion/bronze_ingestion.py` AS WELL AS `python -m`.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.utils.config import load_config
from src.utils.logger import setup_logger, write_ingestion_log
from src.utils.storage import (
    AdlsStorage,
    LayerPaths,
    Storage,
    get_storage,
)

BRONZE_METADATA_COLUMNS = (
    "ingestion_timestamp",
    "source_file_name",
    "batch_id",
    "ingestion_date",
)


# ─────────────────────────────────────────────
# Bronze metadata enrichment
# ─────────────────────────────────────────────


def add_bronze_metadata(
    df: pd.DataFrame,
    source_file: str,
    batch_id: str,
    ingestion_date: str,
) -> pd.DataFrame:
    """Attach the four Bronze audit columns to a freshly-read DataFrame."""
    return df.assign(
        ingestion_timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        source_file_name=source_file,
        batch_id=batch_id,
        ingestion_date=ingestion_date,
    )


# ─────────────────────────────────────────────
# Single-table ingestion
# ─────────────────────────────────────────────


def ingest_table(
    storage: Storage,
    table_config: dict,
    raw_root: str,
    bronze_root: str,
    log_path: str,
    batch_id: str,
    ingestion_date: str,
) -> dict:
    """Ingest one CSV table from raw → bronze on whichever backend `storage` represents."""
    table_name = table_config["name"]
    source_file = table_config["source_file"]
    source_path = f"{raw_root.rstrip('/')}/{source_file}"

    summary: dict = {
        "table": table_name,
        "source_file": source_file,
        "rows_ingested": 0,
        "status": "FAILED",
        "error": "",
    }

    def fail(msg: str, status: str = "FAILED") -> dict:
        (
            logger.error(f"[{table_name}] {msg}")
            if status == "FAILED"
            else logger.warning(f"[{table_name}] {msg}")
        )
        summary["error"] = msg
        summary["status"] = status
        write_ingestion_log(log_path, table_name, source_file, 0, status, msg, batch_id)
        return summary

    # 1. Source file exists?
    if not storage.exists(source_path):
        return fail(f"Source file not found: {source_path}")

    # 2. Read CSV
    try:
        df = storage.read_csv(source_path)
    except Exception as e:  # noqa: BLE001 — surfaced into the run log
        return fail(f"Failed to read CSV: {e}")

    # 3. Empty file?
    if df.empty:
        return fail("CSV file is empty (zero rows)", status="SKIPPED")

    raw_row_count = len(df)
    logger.info(f"[{table_name}] Read {raw_row_count:,} rows from {source_path}")

    # 4. Attach Bronze audit metadata
    df = add_bronze_metadata(df, source_file, batch_id, ingestion_date)

    # 5. Write Hive-partitioned Parquet
    output_path = (
        f"{bronze_root.rstrip('/')}/{table_name}"
        f"/ingestion_date={ingestion_date}/{table_name}_{batch_id}.parquet"
    )
    try:
        written_rows = storage.write_parquet(df, output_path)
    except Exception as e:  # noqa: BLE001
        return fail(f"Failed to write Parquet: {e}")

    logger.success(f"[{table_name}] Ingested {written_rows:,} rows -> {output_path}")
    summary.update({"rows_ingested": written_rows, "status": "SUCCESS"})
    write_ingestion_log(log_path, table_name, source_file, written_rows, "SUCCESS", "", batch_id)
    return summary


# ─────────────────────────────────────────────
# Pipeline runner
# ─────────────────────────────────────────────


def _generate_batch_id() -> tuple[str, str]:
    today = date.today()
    ingestion_date = today.strftime("%Y-%m-%d")
    batch_id = f"batch_{today.strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}"
    return ingestion_date, batch_id


def _summarize(results: list[dict]) -> tuple[list[dict], list[dict], list[dict], int]:
    succeeded = [r for r in results if r["status"] == "SUCCESS"]
    skipped = [r for r in results if r["status"] == "SKIPPED"]
    failed = [r for r in results if r["status"] == "FAILED"]
    total_rows = sum(r["rows_ingested"] for r in succeeded)
    return succeeded, skipped, failed, total_rows


def run_bronze_ingestion(environment: str = "local") -> list[dict]:
    setup_logger()
    logger.info("=" * 60)
    logger.info(f"  Bronze Ingestion Pipeline - Starting ({environment})")
    logger.info("=" * 60)

    config = load_config()
    storage = get_storage(environment, config)
    paths = LayerPaths.from_config(config, environment)

    # `log_path` always lives on the local filesystem — runs are written
    # there first and uploaded to ADLS at the end of the pipeline.
    log_path = config["paths"]["local"]["logs"]
    os.makedirs(log_path, exist_ok=True)

    ingestion_date, batch_id = _generate_batch_id()

    logger.info(f"Backend        : {storage.describe}")
    logger.info(f"Ingestion date : {ingestion_date}")
    logger.info(f"Batch ID       : {batch_id}")
    logger.info(f"Tables to ingest: {len(config['tables'])}")
    logger.info("-" * 60)

    results = [
        ingest_table(
            storage=storage,
            table_config=table_config,
            raw_root=paths.raw,
            bronze_root=paths.bronze,
            log_path=log_path,
            batch_id=batch_id,
            ingestion_date=ingestion_date,
        )
        for table_config in config["tables"]
    ]

    succeeded, skipped, failed, total_rows = _summarize(results)

    logger.info("=" * 60)
    logger.info("  Bronze Ingestion Summary")
    logger.info("=" * 60)
    logger.info(f"Success : {len(succeeded)} tables")
    logger.info(f"Skipped : {len(skipped)} tables")
    logger.info(f"Failed  : {len(failed)} tables")
    logger.info(f"Total rows ingested: {total_rows:,}")

    log_file = os.path.join(log_path, "bronze_ingestion_log.csv")
    logger.info(f"Log written to: {log_file}")

    if isinstance(storage, AdlsStorage):
        remote_log_file = f"{paths.logs.rstrip('/')}/bronze_ingestion_log.csv"
        storage.upload_local_file(log_file, remote_log_file)
        logger.info(f"Log uploaded to ADLS: {remote_log_file}")

    if failed:
        for r in failed:
            logger.warning(f"  - {r['table']}: {r['error']}")

    logger.info("=" * 60)
    logger.info("  Bronze Ingestion Pipeline - Complete")
    logger.info("=" * 60)

    if failed:
        raise RuntimeError("Bronze ingestion failed for: " + ", ".join(r["table"] for r in failed))
    return results


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Bronze ingestion pipeline.")
    parser.add_argument(
        "--environment",
        choices=["local", "azure"],
        default="local",
        help="Run against local filesystem or Azure Data Lake Storage Gen2.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_bronze_ingestion(environment=args.environment)
