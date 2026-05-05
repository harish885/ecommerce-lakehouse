"""
Logging utility for the E-Commerce Lakehouse pipeline.
Writes structured logs to both console and CSV log files.
"""

import csv
import os
from datetime import datetime
from loguru import logger


def setup_logger(log_level: str = "INFO") -> None:
    """Configure loguru logger for console output."""
    logger.remove()
    logger.add(
        sink=lambda msg: print(msg, end=""),
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - <level>{message}</level>",
        colorize=True,
    )


def write_ingestion_log(
    log_path: str,
    table_name: str,
    source_file: str,
    rows_ingested: int,
    status: str,
    error_message: str,
    batch_id: str,
) -> None:
    """Append one row to the bronze ingestion log CSV."""
    os.makedirs(log_path, exist_ok=True)
    log_file = os.path.join(log_path, "bronze_ingestion_log.csv")
    file_exists = os.path.isfile(log_file)

    with open(log_file, "a", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "table_name",
                "source_file",
                "rows_ingested",
                "status",
                "error_message",
                "batch_id",
                "ingestion_timestamp",
            ],
        )
        if not file_exists:
            writer.writeheader()
        writer.writerow(
            {
                "table_name": table_name,
                "source_file": source_file,
                "rows_ingested": rows_ingested,
                "status": status,
                "error_message": error_message,
                "batch_id": batch_id,
                "ingestion_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )


def write_dq_log(
    log_path: str,
    table_name: str,
    rule_id: str,
    rule_description: str,
    total_records: int,
    passed_records: int,
    failed_records: int,
) -> None:
    """Append one row to the data quality report CSV."""
    os.makedirs(log_path, exist_ok=True)
    log_file = os.path.join(log_path, "data_quality_report.csv")
    file_exists = os.path.isfile(log_file)

    pass_rate = round((passed_records / total_records * 100), 2) if total_records > 0 else 0
    if pass_rate >= 99:
        status = "PASS"
    elif pass_rate >= 95:
        status = "WARN"
    else:
        status = "FAIL"

    with open(log_file, "a", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "table_name",
                "rule_id",
                "rule_description",
                "total_records",
                "passed_records",
                "failed_records",
                "pass_rate_pct",
                "status",
                "execution_timestamp",
            ],
        )
        if not file_exists:
            writer.writeheader()
        writer.writerow(
            {
                "table_name": table_name,
                "rule_id": rule_id,
                "rule_description": rule_description,
                "total_records": total_records,
                "passed_records": passed_records,
                "failed_records": failed_records,
                "pass_rate_pct": pass_rate,
                "status": status,
                "execution_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
