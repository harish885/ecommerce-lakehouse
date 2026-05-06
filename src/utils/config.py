"""
Config loader for the medallion lakehouse.

Centralizes the path to `config/config.yaml` and resolves it relative to the
project root, so callers can run pipelines from any working directory.
"""

from __future__ import annotations

from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"


def load_config(config_path: str | Path | None = None) -> dict:
    """Load and return the project YAML config."""
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    with path.open("r") as f:
        return yaml.safe_load(f)
