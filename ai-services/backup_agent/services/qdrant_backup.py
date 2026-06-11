"""
Qdrant backup service using Snapshot API.
"""

import os
import shutil
import time
import json
import asyncio
import httpx
from pathlib import Path
from datetime import datetime
from typing import Any


QDRANT_BASE_URL = os.getenv("QDRANT_URL", "http://localhost:6333")


def get_backup_dir(backup_path: str | None) -> Path:
    if backup_path:
        p = Path(os.path.expanduser(backup_path))
    else:
        p = Path.home() / "Documents" / "backups" / "qdrant"
    p.mkdir(parents=True, exist_ok=True)
    return p


async def _get_collections() -> list[str]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(f"{QDRANT_BASE_URL}/collections")
        r.raise_for_status()
        data = r.json()
        return [c["name"] for c in data["result"]["collections"]]


async def _create_snapshot(collection: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(f"{QDRANT_BASE_URL}/collections/{collection}/snapshots")
        r.raise_for_status()
        data: dict[str, Any] = r.json()
        return dict[str, Any](data["result"])


async def _download_snapshot(collection: str, snapshot_name: str, dest: Path) -> Path:
    async with httpx.AsyncClient(timeout=300.0) as client:
        r = await client.get(
            f"{QDRANT_BASE_URL}/collections/{collection}/snapshots/{snapshot_name}"
        )
        r.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            f.write(r.content)
        return dest


async def _snapshot_collection(collection: str, backup_subdir: Path) -> dict[str, Any]:
    snapshot_info = await _create_snapshot(collection)
    snapshot_name = snapshot_info["name"]
    dest = backup_subdir / f"{collection}_{snapshot_name}"
    await _download_snapshot(collection, snapshot_name, dest)
    return {
        "collection": collection,
        "snapshot_id": snapshot_info.get("id", snapshot_name),
        "snapshot_name": snapshot_name,
        "size_bytes": dest.stat().st_size,
        "size_mb": round(dest.stat().st_size / (1024 * 1024), 2),
    }


async def backup_qdrant_impl(
    backup_path: str | None = None,
    collections: list[str] | None = None,
    retention: int = 7,
) -> dict[str, Any]:
    start = time.time()
    backup_dir = get_backup_dir(backup_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_id = f"qdrant_{timestamp}"
    backup_subdir = backup_dir / backup_id
    backup_subdir.mkdir(parents=True, exist_ok=True)

    try:
        all_collections = await _get_collections()
    except Exception as e:
        return {
            "backup_id": backup_id,
            "status": "failed",
            "duration_seconds": round(time.time() - start, 1),
            "error": f"Cannot connect to Qdrant: {e}",
            "collections": [],
            "snapshots": [],
            "size_mb": 0,
            "size_bytes": 0,
            "created_at": datetime.now().isoformat(),
        }

    target_collections = collections or all_collections
    snapshots = []
    errors = []

    for col in target_collections:
        try:
            snap = await _snapshot_collection(col, backup_subdir)
            snapshots.append(snap)
        except Exception as exc:
            errors.append(f"{col}: {exc}")

    total_size = sum(s["size_bytes"] for s in snapshots)

    result: dict[str, Any] = {
        "backup_id": backup_id,
        "backup_name": backup_id,
        "backup_path": str(backup_subdir),
        "size_mb": round(total_size / (1024 * 1024), 2),
        "size_bytes": total_size,
        "status": "failed" if errors else "completed",
        "duration_seconds": round(time.time() - start, 1),
        "strategy": "manual",
        "collections": target_collections,
        "snapshots": snapshots,
        "errors": errors if errors else None,
        "created_at": datetime.now().isoformat(),
    }

    meta_file = backup_dir / ".meta" / f"{backup_id}.json"
    meta_file.parent.mkdir(exist_ok=True)
    with open(meta_file, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    _cleanup_old(backup_dir, retention)

    return result


def backup_qdrant(
    backup_path: str | None = None,
    collections: list[str] | None = None,
    retention: int = 7,
) -> dict[str, Any]:
    return asyncio.run(backup_qdrant_impl(backup_path, collections, retention))


async def _list_snapshots(collection: str) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(f"{QDRANT_BASE_URL}/collections/{collection}/snapshots")
        if r.status_code == 404:
            return []
        r.raise_for_status()
        data: dict[str, Any] = r.json()
        result: list[dict[str, Any]] = [dict[str, Any](item) for item in data["result"]]
        return result


async def _restore_snapshot(collection: str, snapshot_name: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            f"{QDRANT_BASE_URL}/collections/{collection}/snapshots/{snapshot_name}/recover",
            json={"location": snapshot_name, "mode": {"type": "snapshot"}},
        )
        r.raise_for_status()
        return dict[str, Any](r.json())


def restore_qdrant(backup_id: str, backup_path: str | None = None) -> dict[str, Any]:
    backup_dir = get_backup_dir(backup_path)
    meta_file = backup_dir / ".meta" / f"{backup_id}.json"

    if not meta_file.exists():
        return {
            "restore_id": f"{backup_id}_restore",
            "status": "failed",
            "duration_seconds": 0,
            "collections_restored": [],
            "error": f"Backup metadata not found: {meta_file}",
        }

    with open(meta_file) as f:
        meta = json.load(f)

    snapshots = meta.get("snapshots", [])
    restored = []
    errors = []

    for snap in snapshots:
        try:
            asyncio.run(_restore_snapshot(snap["collection"], snap["snapshot_name"]))
            restored.append(snap["collection"])
        except Exception as e:
            errors.append(f"{snap['collection']}: {e}")

    return {
        "restore_id": f"{backup_id}_restore",
        "status": "failed" if errors else "completed",
        "duration_seconds": 0,
        "collections_restored": restored,
        "errors": errors if errors else None,
    }


def get_qdrant_history(backup_path: str | None = None) -> list[dict[str, Any]]:
    backup_dir = get_backup_dir(backup_path)
    history = []
    meta_dir = backup_dir / ".meta"
    for f in sorted(
        meta_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
    ):
        with open(f) as fp:
            history.append(json.load(fp))
    return history


def delete_qdrant_backup(
    backup_id: str, backup_path: str | None = None
) -> dict[str, Any]:
    backup_dir = get_backup_dir(backup_path)
    backup_subdir = backup_dir / backup_id
    meta_file = backup_dir / ".meta" / f"{backup_id}.json"

    deleted: list[str] = []
    errors: list[str] = []

    if backup_subdir.exists() and backup_subdir.is_dir():
        shutil.rmtree(backup_subdir)
        deleted.append(str(backup_subdir))
    elif (backup_dir / f"{backup_id}.tar.gz").exists():
        (backup_dir / f"{backup_id}.tar.gz").unlink()
        deleted.append(str(backup_dir / f"{backup_id}.tar.gz"))

    if meta_file.exists():
        meta_file.unlink()
        deleted.append(str(meta_file))

    return {
        "backup_id": backup_id,
        "deleted": deleted,
        "errors": errors,
        "status": "failed" if errors else "deleted",
    }


def get_disk_usage(backup_path: str | None) -> dict[str, Any]:
    backup_dir = get_backup_dir(backup_path)
    stat = shutil.disk_usage(backup_dir)
    total_gb = round(stat.total / (1024**3), 2)
    used_gb = round(stat.used / (1024**3), 2)
    free_gb = round(stat.free / (1024**3), 2)
    usage_percent = round((stat.used / stat.total) * 100, 1)
    return {
        "total_gb": total_gb,
        "used_gb": used_gb,
        "free_gb": free_gb,
        "usage_percent": usage_percent,
    }


def _cleanup_old(backup_dir: Path, retention: int) -> None:
    meta_dir = backup_dir / ".meta"
    backups = sorted(meta_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
    for old in backups[:-retention]:
        backup_subdir = backup_dir / old.stem
        if backup_subdir.exists() and backup_subdir.is_dir():
            shutil.rmtree(backup_subdir)
        old.unlink()
