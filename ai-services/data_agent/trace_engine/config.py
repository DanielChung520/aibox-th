"""
@file        config.py
@description Configuration loader for the Trace Engine.
             Reads batch_fields_config.json and exposes typed config objects.
@lastUpdate  2026-05-17
@author      Daniel Chung
@version     1.0.0
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel, Field


class BatchFieldInfo(BaseModel):
    """Metadata for a batch/date field used in trace scenarios."""

    table_key: str
    table_name: str
    field_id: str
    field_name: str
    field_type: str = ""
    description: str = ""
    confidence: str = "high"


class TableMeta(BaseModel):
    """Minimal table metadata for the trace engine."""

    name: str
    module: str = ""


class EssentialPath(BaseModel):
    """A known-important traversal path in the trace graph."""

    model_config = {"populate_by_name": True}

    from_: str = Field(alias="from")
    from_name: str = ""
    to: str
    to_name: str = ""
    via: str
    description: str = ""


class TraceEngineConfig(BaseModel):
    """Aggregated configuration for the trace engine."""

    batch_fields: list[BatchFieldInfo] = []
    date_fields: list[BatchFieldInfo] = []
    tables_meta: dict[str, TableMeta] = {}
    essential_paths: dict[str, EssentialPath] = {}


def load_config(config_path: str | None = None) -> TraceEngineConfig:
    """Load trace engine configuration from a JSON file.

    Args:
        config_path: Absolute path to batch_fields_config.json.
                     Defaults to ``<this_dir>/batch_fields_config.json``.

    Returns:
        A populated ``TraceEngineConfig`` instance, or an empty config
        when the file does not exist.
    """
    if config_path is None:
        config_path = str(Path(__file__).parent / "batch_fields_config.json")
    if not os.path.exists(config_path):
        return TraceEngineConfig()
    with open(config_path) as f:
        data = json.load(f)
    return TraceEngineConfig(
        batch_fields=[BatchFieldInfo(**b) for b in data.get("batch_fields", [])],
        date_fields=[BatchFieldInfo(**d) for d in data.get("date_fields", [])],
        tables_meta={k: TableMeta(**v) for k, v in data.get("tables_meta", {}).items()},
        essential_paths={k: EssentialPath(**v) for k, v in data.get("essential_paths", {}).items()},
    )
