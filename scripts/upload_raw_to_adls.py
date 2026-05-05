"""
Upload local Olist raw CSV files to Azure Data Lake Storage Gen2.

Prerequisites:
    az login
    pip install -r requirements.txt

Usage:
    python scripts/upload_raw_to_adls.py
"""

import sys
from pathlib import Path

import yaml
from azure.identity import AzureCliCredential
from azure.storage.filedatalake import DataLakeServiceClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def load_config() -> dict:
    with open(PROJECT_ROOT / "config" / "config.yaml", "r") as f:
        return yaml.safe_load(f)


def ensure_directory(file_system_client, directory_path: str):
    current = ""
    for part in directory_path.split("/"):
        current = part if not current else f"{current}/{part}"
        directory_client = file_system_client.get_directory_client(current)
        try:
            directory_client.create_directory()
        except Exception as exc:
            if "ResourceAlreadyExists" not in str(exc):
                raise


def upload_file(file_system_client, local_file: Path, remote_path: str):
    file_client = file_system_client.get_file_client(remote_path)
    with open(local_file, "rb") as data:
        file_client.upload_data(data, overwrite=True)


def main():
    config = load_config()
    local_raw = PROJECT_ROOT / config["paths"]["local"]["raw"]
    azure_config = config["paths"]["azure"]

    account_name = azure_config["storage_account"]
    container = azure_config["container"]
    raw_prefix = azure_config["raw_prefix"].strip("/")

    if not local_raw.exists():
        raise FileNotFoundError(f"Local raw folder not found: {local_raw}")

    account_url = f"https://{account_name}.dfs.core.windows.net"
    credential = AzureCliCredential()
    service_client = DataLakeServiceClient(account_url=account_url, credential=credential)
    file_system_client = service_client.get_file_system_client(container)

    ensure_directory(file_system_client, raw_prefix)

    csv_files = sorted(local_raw.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {local_raw}")

    print(
        f"Uploading {len(csv_files)} CSV files to abfss://{container}@{account_name}.dfs.core.windows.net/{raw_prefix}/"
    )
    for csv_file in csv_files:
        remote_path = f"{raw_prefix}/{csv_file.name}"
        upload_file(file_system_client, csv_file, remote_path)
        print(f"uploaded {csv_file.name} -> {remote_path}")

    print("Raw upload complete.")


if __name__ == "__main__":
    main()
