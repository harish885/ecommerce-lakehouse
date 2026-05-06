"""
Storage abstraction for the medallion lakehouse.

Provides a single interface (`Storage`) over both the local filesystem and
Azure Data Lake Storage Gen2, so the Bronze, Silver, and Gold pipelines have
one code path instead of two parallel branches (one per environment).

Conventions
-----------
Paths passed to a `Storage` are POSIX-style, relative to the storage root:

    bronze/olist/orders/ingestion_date=2026-05-05/orders_<batch>.parquet

`LayerPaths` resolves the medallion roots from `config/config.yaml` for the
chosen environment, so callers never branch on local vs azure themselves.
"""

from __future__ import annotations

import io
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass

import pandas as pd
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.identity import AzureCliCredential
from azure.storage.filedatalake import DataLakeServiceClient, FileSystemClient


# ─────────────────────────────────────────────
# Layer path resolution
# ─────────────────────────────────────────────


@dataclass(frozen=True)
class LayerPaths:
    """Roots of each medallion layer for a given environment."""

    raw: str
    bronze: str
    silver: str
    gold: str
    rejected: str
    logs: str

    @classmethod
    def from_config(cls, config: dict, environment: str) -> "LayerPaths":
        if environment == "local":
            local = config["paths"]["local"]
            return cls(
                raw=local["raw"],
                bronze=local["bronze"],
                silver=local["silver"],
                gold=local["gold"],
                rejected=local["rejected"],
                logs=local["logs"],
            )
        if environment == "azure":
            azure = config["paths"]["azure"]
            return cls(
                raw=azure["raw_prefix"],
                bronze=azure["bronze_prefix"],
                silver=azure["silver_prefix"],
                gold=azure["gold_prefix"],
                rejected=azure["rejected_prefix"],
                logs=azure["logs_prefix"],
            )
        raise ValueError(f"Unknown environment: {environment!r}")


# ─────────────────────────────────────────────
# Storage protocol
# ─────────────────────────────────────────────


class Storage(ABC):
    """Filesystem-like backend used by Bronze / Silver / Gold pipelines."""

    @abstractmethod
    def exists(self, path: str) -> bool:
        """Return True if the file exists at `path`."""

    @abstractmethod
    def read_csv(self, path: str) -> pd.DataFrame:
        """Read a CSV file."""

    @abstractmethod
    def read_parquet(self, path: str) -> pd.DataFrame:
        """Read a single Parquet file."""

    @abstractmethod
    def read_parquet_dataset(self, paths: list[str]) -> pd.DataFrame:
        """Read and concatenate multiple Parquet files."""

    @abstractmethod
    def write_parquet(self, df: pd.DataFrame, path: str) -> int:
        """Write a DataFrame as Parquet and return the row count of the persisted file."""

    @abstractmethod
    def list_partitions(self, dir_path: str, prefix: str = "ingestion_date=") -> list[str]:
        """Return Hive-style partition directory names under `dir_path`, newest first."""

    @abstractmethod
    def list_parquet_files(self, dir_path: str) -> list[str]:
        """Return all Parquet file paths directly inside `dir_path`."""

    @abstractmethod
    def upload_local_file(self, local_path: str, remote_path: str) -> None:
        """Copy a local file to `remote_path`. No-op when the backend IS local."""

    @property
    @abstractmethod
    def describe(self) -> str:
        """Human-readable description of this backend (used for logging)."""


# ─────────────────────────────────────────────
# Local filesystem backend
# ─────────────────────────────────────────────


class LocalStorage(Storage):
    """Local filesystem backend. `path` is treated as a relative or absolute path."""

    def exists(self, path: str) -> bool:
        return os.path.isfile(path)

    def read_csv(self, path: str) -> pd.DataFrame:
        return pd.read_csv(path, low_memory=False)

    def read_parquet(self, path: str) -> pd.DataFrame:
        return pd.read_parquet(path)

    def read_parquet_dataset(self, paths: list[str]) -> pd.DataFrame:
        if not paths:
            raise FileNotFoundError("No Parquet files supplied to read_parquet_dataset")
        return pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True)

    def write_parquet(self, df: pd.DataFrame, path: str) -> int:
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        df.to_parquet(path, index=False, engine="pyarrow")
        return len(pd.read_parquet(path))

    def list_partitions(self, dir_path: str, prefix: str = "ingestion_date=") -> list[str]:
        if not os.path.isdir(dir_path):
            return []
        return sorted(
            (d for d in os.listdir(dir_path) if d.startswith(prefix)),
            reverse=True,
        )

    def list_parquet_files(self, dir_path: str) -> list[str]:
        if not os.path.isdir(dir_path):
            return []
        return sorted(
            os.path.join(dir_path, f) for f in os.listdir(dir_path) if f.endswith(".parquet")
        )

    def upload_local_file(self, local_path: str, remote_path: str) -> None:
        # The source already IS the local filesystem — nothing to upload.
        return None

    @property
    def describe(self) -> str:
        return "local filesystem"


# ─────────────────────────────────────────────
# Azure Data Lake Storage Gen2 backend
# ─────────────────────────────────────────────


class AdlsStorage(Storage):
    """ADLS Gen2 backend authenticated via `az login` (AzureCliCredential)."""

    def __init__(self, account_name: str, file_system: str) -> None:
        self._account_name = account_name
        self._file_system = file_system
        account_url = f"https://{account_name}.dfs.core.windows.net"
        credential = AzureCliCredential()
        service_client = DataLakeServiceClient(account_url=account_url, credential=credential)
        self._fs: FileSystemClient = service_client.get_file_system_client(file_system)

    @classmethod
    def from_config(cls, azure_config: dict) -> "AdlsStorage":
        return cls(
            account_name=azure_config["storage_account"],
            file_system=azure_config["container"],
        )

    # ── helpers ────────────────────────────────────────────

    def _ensure_directory(self, dir_path: str) -> None:
        if not dir_path:
            return
        current = ""
        for part in dir_path.strip("/").split("/"):
            current = part if not current else f"{current}/{part}"
            try:
                self._fs.get_directory_client(current).create_directory()
            except ResourceExistsError:
                pass

    # ── interface ──────────────────────────────────────────

    def exists(self, path: str) -> bool:
        try:
            self._fs.get_file_client(path).get_file_properties()
            return True
        except ResourceNotFoundError:
            return False

    def read_csv(self, path: str) -> pd.DataFrame:
        data = self._fs.get_file_client(path).download_file().readall()
        return pd.read_csv(io.BytesIO(data), low_memory=False)

    def read_parquet(self, path: str) -> pd.DataFrame:
        data = self._fs.get_file_client(path).download_file().readall()
        return pd.read_parquet(io.BytesIO(data))

    def read_parquet_dataset(self, paths: list[str]) -> pd.DataFrame:
        if not paths:
            raise FileNotFoundError("No Parquet files supplied to read_parquet_dataset")
        return pd.concat([self.read_parquet(p) for p in paths], ignore_index=True)

    def write_parquet(self, df: pd.DataFrame, path: str) -> int:
        self._ensure_directory(os.path.dirname(path))
        buffer = io.BytesIO()
        df.to_parquet(buffer, index=False, engine="pyarrow")
        buffer.seek(0)
        self._fs.get_file_client(path).upload_data(buffer.getvalue(), overwrite=True)
        return len(self.read_parquet(path))

    def list_partitions(self, dir_path: str, prefix: str = "ingestion_date=") -> list[str]:
        try:
            paths = list(self._fs.get_paths(path=dir_path))
        except ResourceNotFoundError:
            return []
        partitions: set[str] = set()
        base = dir_path.rstrip("/") + "/"
        for path in paths:
            relative = path.name[len(base) :] if path.name.startswith(base) else path.name
            partition = relative.split("/", 1)[0]
            if partition.startswith(prefix):
                partitions.add(partition)
        return sorted(partitions, reverse=True)

    def list_parquet_files(self, dir_path: str) -> list[str]:
        try:
            return sorted(
                p.name for p in self._fs.get_paths(path=dir_path) if p.name.endswith(".parquet")
            )
        except ResourceNotFoundError:
            return []

    def upload_local_file(self, local_path: str, remote_path: str) -> None:
        if not os.path.isfile(local_path):
            return
        self._ensure_directory(os.path.dirname(remote_path))
        with open(local_path, "rb") as f:
            self._fs.get_file_client(remote_path).upload_data(f.read(), overwrite=True)

    @property
    def describe(self) -> str:
        return f"abfss://{self._file_system}@{self._account_name}.dfs.core.windows.net/"


# ─────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────


def get_storage(environment: str, config: dict) -> Storage:
    """Return the `Storage` backend for `environment` ('local' or 'azure')."""
    if environment == "local":
        return LocalStorage()
    if environment == "azure":
        return AdlsStorage.from_config(config["paths"]["azure"])
    raise ValueError(f"Unknown environment: {environment!r}")
