"""
Upload local Olist raw CSV files to Azure Data Lake Storage Gen2.

This is a one-shot bootstrap utility — once raw CSVs live in ADLS, the
Bronze ingestion pipeline reads them directly with `--environment azure`.

Prerequisites
-------------
    az login
    pip install -r requirements.txt

Usage
-----
    python scripts/upload_raw_to_adls.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.config import load_config  # noqa: E402
from src.utils.storage import AdlsStorage  # noqa: E402


def main() -> None:
    config = load_config()
    azure = config["paths"]["azure"]
    raw_prefix = azure["raw_prefix"].strip("/")

    local_raw = PROJECT_ROOT / config["paths"]["local"]["raw"]
    if not local_raw.exists():
        raise FileNotFoundError(f"Local raw folder not found: {local_raw}")

    csv_files = sorted(local_raw.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {local_raw}")

    storage = AdlsStorage.from_config(azure)
    print(f"Uploading {len(csv_files)} CSV files to {storage.describe}{raw_prefix}/")

    for csv_file in csv_files:
        remote_path = f"{raw_prefix}/{csv_file.name}"
        storage.upload_local_file(str(csv_file), remote_path)
        print(f"uploaded {csv_file.name} -> {remote_path}")

    print("Raw upload complete.")


if __name__ == "__main__":
    main()
