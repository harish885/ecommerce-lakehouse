"""
Bronze Layer Ingestion Pipeline
================================
Reads raw CSV files, adds metadata columns, and writes Parquet files
to the Bronze layer. Supports local filesystem and Azure Data Lake Storage Gen2.

Usage:
    python src/ingestion/bronze_ingestion.py
    python src/ingestion/bronze_ingestion.py --environment azure

Output:
    data/bronze/{table}/ingestion_date=YYYY-MM-DD/{table}_{batch_id}.parquet
    abfss://{container}@{account}.dfs.core.windows.net/bronze/olist/{table}/...
    logs/bronze_ingestion_log.csv
"""

import argparse
import io
import os
import sys
import uuid
from datetime import datetime, date

import pandas as pd
import yaml
from loguru import logger

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.identity import AzureCliCredential
from azure.storage.filedatalake import DataLakeServiceClient

# Allow imports from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from src.utils.logger import setup_logger, write_ingestion_log


# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────


def load_config(config_path: str = "config/config.yaml") -> dict:
    with open(config_path, "r") as f:
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


def adls_file_exists(file_system_client, file_path: str) -> bool:
    try:
        file_system_client.get_file_client(file_path).get_file_properties()
        return True
    except ResourceNotFoundError:
        return False


def read_adls_csv(file_system_client, file_path: str) -> pd.DataFrame:
    file_client = file_system_client.get_file_client(file_path)
    data = file_client.download_file().readall()
    return pd.read_csv(io.BytesIO(data), low_memory=False)


def write_adls_parquet(file_system_client, df: pd.DataFrame, file_path: str) -> int:
    directory_path = os.path.dirname(file_path)
    ensure_adls_directory(file_system_client, directory_path)

    buffer = io.BytesIO()
    df.to_parquet(buffer, index=False, engine="pyarrow")
    buffer.seek(0)

    file_client = file_system_client.get_file_client(file_path)
    file_client.upload_data(buffer.getvalue(), overwrite=True)

    written_data = file_client.download_file().readall()
    written_df = pd.read_parquet(io.BytesIO(written_data))
    return len(written_df)


def upload_log_to_adls(file_system_client, local_log_file: str, remote_log_file: str) -> None:
    if not os.path.exists(local_log_file):
        return
    ensure_adls_directory(file_system_client, os.path.dirname(remote_log_file))
    with open(local_log_file, "rb") as f:
        file_system_client.get_file_client(remote_log_file).upload_data(f.read(), overwrite=True)


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

    logger.success(f"[{table_name}] ✅ Ingested {written_rows:,} rows → {output_file}")

    # ── 8. Log result ────────────────────────────────────────
    summary.update({"rows_ingested": written_rows, "status": "SUCCESS", "error": ""})
    write_ingestion_log(log_path, table_name, source_file, written_rows, "SUCCESS", "", batch_id)

    return summary


def ingest_table_azure(
    table_config: dict,
    file_system_client,
    raw_prefix: str,
    bronze_prefix: str,
    log_path: str,
    batch_id: str,
    ingestion_date: str,
) -> dict:
    """
    Ingest one CSV table from ADLS Raw to ADLS Bronze.

    Returns a summary dict with status, rows, and any error.
    """
    table_name = table_config["name"]
    source_file = table_config["source_file"]
    source_path = f"{raw_prefix.strip('/')}/{source_file}"

    summary = {
        "table": table_name,
        "source_file": source_file,
        "rows_ingested": 0,
        "status": "FAILED",
        "error": "",
    }

    if not adls_file_exists(file_system_client, source_path):
        msg = f"ADLS source file not found: {source_path}"
        logger.error(f"[{table_name}] {msg}")
        summary["error"] = msg
        write_ingestion_log(log_path, table_name, source_file, 0, "FAILED", msg, batch_id)
        return summary

    try:
        df = read_adls_csv(file_system_client, source_path)
    except Exception as e:
        msg = f"Failed to read ADLS CSV: {e}"
        logger.error(f"[{table_name}] {msg}")
        summary["error"] = msg
        write_ingestion_log(log_path, table_name, source_file, 0, "FAILED", msg, batch_id)
        return summary

    if df.empty:
        msg = "CSV file is empty (zero rows)"
        logger.warning(f"[{table_name}] {msg}")
        summary["status"] = "SKIPPED"
        summary["error"] = msg
        write_ingestion_log(log_path, table_name, source_file, 0, "SKIPPED", msg, batch_id)
        return summary

    raw_row_count = len(df)
    logger.info(f"[{table_name}] Read {raw_row_count:,} rows from ADLS {source_path}")

    ingestion_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df["ingestion_timestamp"] = ingestion_ts
    df["source_file_name"] = source_file
    df["batch_id"] = batch_id
    df["ingestion_date"] = ingestion_date

    output_file = (
        f"{bronze_prefix.strip('/')}/{table_name}/"
        f"ingestion_date={ingestion_date}/{table_name}_{batch_id}.parquet"
    )

    try:
        written_rows = write_adls_parquet(file_system_client, df, output_file)
    except Exception as e:
        msg = f"Failed to write ADLS Parquet: {e}"
        logger.error(f"[{table_name}] {msg}")
        summary["error"] = msg
        write_ingestion_log(log_path, table_name, source_file, 0, "FAILED", msg, batch_id)
        return summary

    logger.success(f"[{table_name}] Ingested {written_rows:,} rows -> ADLS {output_file}")

    summary.update({"rows_ingested": written_rows, "status": "SUCCESS", "error": ""})
    write_ingestion_log(log_path, table_name, source_file, written_rows, "SUCCESS", "", batch_id)

    return summary


# ─────────────────────────────────────────────
# Main pipeline runner
# ─────────────────────────────────────────────


def run_bronze_ingestion(environment: str = "local"):
    setup_logger()

    logger.info("=" * 60)
    logger.info(f"  Bronze Ingestion Pipeline - Starting ({environment})")
    logger.info("=" * 60)

    # Load config
    config = load_config()
    raw_path = config["paths"]["local"]["raw"]
    bronze_path = config["paths"]["local"]["bronze"]
    log_path = config["paths"]["local"]["logs"]
    tables = config["tables"]
    azure_config = config["paths"]["azure"]

    if environment not in ["local", "azure"]:
        raise ValueError("environment must be either 'local' or 'azure'")

    os.makedirs(log_path, exist_ok=True)

    # Generate batch identifiers
    ingestion_date = date.today().strftime("%Y-%m-%d")
    batch_id = f"batch_{date.today().strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}"

    logger.info(f"Ingestion date : {ingestion_date}")
    logger.info(f"Batch ID       : {batch_id}")
    logger.info(f"Environment    : {environment}")
    logger.info(f"Tables to ingest: {len(tables)}")
    logger.info("-" * 60)

    file_system_client = None
    if environment == "azure":
        file_system_client = get_adls_file_system_client(azure_config)
        logger.info(
            "ADLS target    : "
            f"abfss://{azure_config['container']}@"
            f"{azure_config['storage_account']}.dfs.core.windows.net/"
        )

    results = []
    for table_config in tables:
        if environment == "azure":
            result = ingest_table_azure(
                table_config=table_config,
                file_system_client=file_system_client,
                raw_prefix=azure_config["raw_prefix"],
                bronze_prefix=azure_config["bronze_prefix"],
                log_path=log_path,
                batch_id=batch_id,
                ingestion_date=ingestion_date,
            )
        else:
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
    log_file = os.path.join(log_path, "bronze_ingestion_log.csv")
    logger.info(f"Log written to: {log_file}")

    if environment == "azure" and file_system_client is not None:
        remote_log_file = f"{azure_config['logs_prefix'].strip('/')}/bronze_ingestion_log.csv"
        upload_log_to_adls(file_system_client, log_file, remote_log_file)
        logger.info(f"Log uploaded to ADLS: {remote_log_file}")

    if failed:
        logger.warning("Failed tables:")
        for r in failed:
            logger.warning(f"  - {r['table']}: {r['error']}")

    logger.info("=" * 60)
    logger.info("  Bronze Ingestion Pipeline - Complete")
    logger.info("=" * 60)

    if failed:
        failed_tables = ", ".join(r["table"] for r in failed)
        raise RuntimeError(f"Bronze ingestion failed for: {failed_tables}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Bronze ingestion pipeline.")
    parser.add_argument(
        "--environment",
        choices=["local", "azure"],
        default="local",
        help="Run against local filesystem or Azure Data Lake Storage Gen2.",
    )
    args = parser.parse_args()
    run_bronze_ingestion(environment=args.environment)
