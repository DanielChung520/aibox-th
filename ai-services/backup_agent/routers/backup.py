"""
Backup API routes - ArangoDB & Qdrant endpoints.
"""

import logging
from fastapi import APIRouter, HTTPException
from typing import Any
from pydantic import BaseModel

from backup_agent.services.arangodb_backup import (
    backup_arangodb,
    restore_arangodb,
    delete_backup as arango_delete,
    get_backup_history as arango_history,
    get_disk_usage as arango_disk_usage,
)
from backup_agent.services.qdrant_backup import (
    backup_qdrant,
    restore_qdrant,
    delete_qdrant_backup,
    get_qdrant_history,
    get_disk_usage as qdrant_disk_usage,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/backup", tags=["Backup"])


# ─── Shared ───────────────────────────────────────────────────────────────


class BackupReq(BaseModel):
    backup_path: str | None = None
    retention: int = 7
    collections: list[str] | None = None


class RestoreReq(BaseModel):
    backup_id: str
    collection_name: str | None = None


# ─── ArangoDB ────────────────────────────────────────────────────────────


@router.post("/arangodb")
def create_arangodb_backup(req: BackupReq) -> dict[str, Any]:
    logger.info("Starting ArangoDB backup, path=%s", req.backup_path)
    result = backup_arangodb(backup_path=req.backup_path, retention=req.retention)
    if result["status"] == "failed":
        raise HTTPException(
            status_code=500, detail=result.get("error", "Backup failed")
        )
    return result


@router.post("/arangodb/restore")
def restore_arangodb_backup(req: RestoreReq) -> dict[str, Any]:
    logger.warning("Restoring ArangoDB from backup=%s", req.backup_id)
    result = restore_arangodb(backup_id=req.backup_id)
    if result["status"] == "failed":
        raise HTTPException(
            status_code=400, detail=result.get("error", "Restore failed")
        )
    return result


@router.get("/arangodb/history")
def list_arangodb_backups() -> dict[str, Any]:
    history = arango_history(backup_path=None)
    return {"code": 0, "data": history}


@router.delete("/arangodb/{backup_id}")
def delete_arangodb_backup(backup_id: str) -> dict[str, Any]:
    result = arango_delete(backup_id=backup_id)
    return result


@router.get("/arangodb/disk-usage")
def arango_usage() -> dict[str, Any]:
    usage = arango_disk_usage(backup_path=None)
    return {"code": 0, "data": usage}


# ─── Qdrant ──────────────────────────────────────────────────────────────


@router.post("/qdrant")
def create_qdrant_backup(req: BackupReq) -> dict[str, Any]:
    logger.info(
        "Starting Qdrant backup, path=%s, collections=%s",
        req.backup_path,
        req.collections,
    )
    result = backup_qdrant(
        backup_path=req.backup_path,
        collections=req.collections,
        retention=req.retention,
    )
    if result["status"] == "failed":
        raise HTTPException(
            status_code=500, detail=result.get("error", "Backup failed")
        )
    return result


@router.post("/qdrant/restore")
def restore_qdrant_backup(req: RestoreReq) -> dict[str, Any]:
    logger.warning("Restoring Qdrant from backup=%s", req.backup_id)
    result = restore_qdrant(backup_id=req.backup_id)
    if result["status"] == "failed":
        raise HTTPException(
            status_code=400, detail=result.get("error", "Restore failed")
        )
    return result


@router.get("/qdrant/history")
def list_qdrant_backups() -> dict[str, Any]:
    history = get_qdrant_history(backup_path=None)
    return {"code": 0, "data": history}


@router.delete("/qdrant/{backup_id}")
def delete_qdrant_backup_route(backup_id: str) -> dict[str, Any]:
    result = delete_qdrant_backup(backup_id=backup_id)
    return result


@router.get("/qdrant/disk-usage")
def qdrant_usage() -> dict[str, Any]:
    usage = qdrant_disk_usage(backup_path=None)
    return {"code": 0, "data": usage}


# ─── Status ─────────────────────────────────────────────────────────────


@router.get("/status")
def backup_status() -> dict[str, Any]:
    arango = arango_disk_usage(backup_path=None)
    qdrant = qdrant_disk_usage(backup_path=None)
    return {
        "code": 0,
        "data": {
            "arangodb": arango,
            "qdrant": qdrant,
        },
    }
