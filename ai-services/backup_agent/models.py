"""
Backup Agent Service - ArangoDB & Qdrant Backup Management

# Last Update: 2026-04-04
# Author: Daniel Chung
# Version: 1.0.0
"""

from pydantic import BaseModel
from typing import Optional


class BackupRequest(BaseModel):
    backup_path: Optional[str] = None
    retention: int = 7
    collections: Optional[list[str]] = None


class RestoreRequest(BaseModel):
    backup_id: str
    target_mode: str = "overwrite"
    collection_name: Optional[str] = None


class BackupResult(BaseModel):
    backup_id: str
    backup_name: str
    backup_path: str
    size_mb: float
    size_bytes: int
    status: str
    duration_seconds: float
    strategy: str = "manual"
    collections_count: int = 0
    created_at: str
    error: Optional[str] = None


class RestoreResult(BaseModel):
    restore_id: str
    status: str
    duration_seconds: float
    collections_restored: list[str]
    error: Optional[str] = None


class DiskUsage(BaseModel):
    total_gb: float
    used_gb: float
    free_gb: float
    usage_percent: float


class BackupHistoryItem(BaseModel):
    backup_id: str
    database: str
    backup_name: str
    backup_path: str
    size_mb: float
    size_bytes: int
    status: str
    duration_seconds: float
    strategy: str
    created_at: str
