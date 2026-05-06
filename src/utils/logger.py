"""
Logging utilities for the medallion lakehouse.

Two responsibilities:

1. Configure `loguru` for human-readable console output.
2. Append structured run logs (CSV) for the Bronze, Silver, and Gold stages.

The CSV writers all share a single helper so adding a new run log is a
one-line change.
"""

from __future__ import annotations

import csv
import os
from datetime import datetime
from typing import Iterable, Mapping

from loguru import logger

# ─────────────────────────────────────────────
# Console logger
# ─────────────────────────────────────────────

_LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan> - <level>{message}</level>"
)


def setup_logger(log_level: str = "INFO") -> None:
    """Configure loguru for colourful console output."""
    logger.remove()
    logger.add(
        sink=lambda msg: print(msg, end=""),
        level=log_level,
        format=_LOG_FORMAT,
        colorize=True,
    )


# ─────────────────────────────────────────────
# CSV append helper
# ─────────────────────────────────────────────


def _append_csv_row(log_file: str, fieldnames: Iterable[str], row: Mapping[str, object]) -> None:
    """Append one dict row to a CSV file, writing the header if the file is new."""
    log_dir = os.path.dirname(log_file)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    file_exists = os.path.isfile(log_file)
    with open(log_file, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(fieldnames))
        if not file_exists:
            writer.writeheader()
        writer.writerow(dict(row))


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ─────────────────────────────────────────────
# Run logs (one writer per pipeline stage)
# ─────────────────────────────────────────────


_BRONZE_FIELDS = (
    "table_name",
    "source_file",
    "rows_ingested",
    "status",
    "error_message",
    "batch_id",
    "ingestion_timestamp",
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
    _append_csv_row(
        os.path.join(log_path, "bronze_ingestion_log.csv"),
        _BRONZE_FIELDS,
        {
            "table_name": table_name,
            "source_file": source_file,
            "rows_ingested": rows_ingested,
            "status": status,
            "error_message": error_message,
            "batch_id": batch_id,
            "ingestion_timestamp": _now(),
        },
    )


_DQ_FIELDS = (
    "table_name",
    "rule_id",
    "rule_description",
    "total_records",
    "passed_records",
    "failed_records",
    "pass_rate_pct",
    "status",
    "execution_timestamp",
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
    pass_rate = round((passed_records / total_records * 100), 2) if total_records else 0
    if pass_rate >= 99:
        status = "PASS"
    elif pass_rate >= 95:
        status = "WARN"
    else:
        status = "FAIL"

    _append_csv_row(
        os.path.join(log_path, "data_quality_report.csv"),
        _DQ_FIELDS,
        {
            "table_name": table_name,
            "rule_id": rule_id,
            "rule_description": rule_description,
            "total_records": total_records,
            "passed_records": passed_records,
            "failed_records": failed_records,
            "pass_rate_pct": pass_rate,
            "status": status,
            "execution_timestamp": _now(),
        },
    )


_GOLD_FIELDS = (
    "table_name",
    "rows_written",
    "status",
    "error_message",
    "execution_timestamp",
)


def write_gold_log(
    log_path: str,
    table_name: str,
    rows_written: int,
    status: str,
    error: str = "",
) -> None:
    """Append one row to the gold transformation log CSV."""
    _append_csv_row(
        os.path.join(log_path, "gold_transformation_log.csv"),
        _GOLD_FIELDS,
        {
            "table_name": table_name,
            "rows_written": rows_written,
            "status": status,
            "error_message": error,
            "execution_timestamp": _now(),
        },
    )
