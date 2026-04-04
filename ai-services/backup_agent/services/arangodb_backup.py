"""
ArangoDB backup service using Docker volume snapshot.
"""

import os
import subprocess
import time
import shutil
from pathlib import Path
from datetime import datetime
from typing import Any


ARANGO_VOLUME_NAME = "aibox_arango-data"


def get_docker_volume_path(volume_name: str) -> str:
    result = subprocess.run(
        ["docker", "volume", "inspect", volume_name, "--format", "{{.Mountpoint}}"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def get_backup_dir(backup_path: str | None) -> Path:
    if backup_path:
        p = Path(os.path.expanduser(backup_path))
    else:
        p = Path.home() / "Documents" / "backups" / "arangodb"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_backup_history(backup_path: str | None) -> list[dict[str, Any]]:
    backup_dir = get_backup_dir(backup_path)
    history = []
    meta_dir = backup_dir / ".meta"
    meta_dir.mkdir(exist_ok=True)
    for f in sorted(
        meta_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
    ):
        import json

        with open(f) as fp:
            history.append(json.load(fp))
    return history


def _save_meta(backup_dir: Path, result: dict[str, Any]) -> None:
    meta_dir = backup_dir / ".meta"
    meta_dir.mkdir(exist_ok=True)
    import json

    meta_file = meta_dir / f"{result['backup_id']}.json"
    with open(meta_file, "w") as fp:
        json.dump(result, fp, ensure_ascii=False, indent=2)


def _cleanup_old(backup_dir: Path, retention: int) -> None:
    meta_dir = backup_dir / ".meta"
    backups = sorted(meta_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
    for old in backups[:-retention]:
        backup_file = backup_dir / old.stem
        if backup_file.exists():
            backup_file.unlink()
        old.unlink()


def backup_arangodb(
    backup_path: str | None = None, retention: int = 7
) -> dict[str, Any]:
    start = time.time()
    backup_dir = get_backup_dir(backup_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_id = f"arangodb_{timestamp}"
    backup_file = backup_dir / f"{backup_id}.tar.gz"

    try:
        get_docker_volume_path(ARANGO_VOLUME_NAME)
    except subprocess.CalledProcessError:
        return {
            "backup_id": backup_id,
            "backup_name": f"{backup_id}.tar.gz",
            "backup_path": str(backup_file),
            "size_mb": 0,
            "size_bytes": 0,
            "status": "failed",
            "duration_seconds": round(time.time() - start, 1),
            "strategy": "manual",
            "collections_count": 0,
            "created_at": datetime.now().isoformat(),
            "error": "ArangoDB volume not found or Docker not running",
        }

    try:
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{ARANGO_VOLUME_NAME}:/src:ro",
                "-v",
                f"{backup_dir}:/dst",
                "alpine",
                "tar",
                "czf",
                f"/dst/{backup_id}.tar.gz",
                "-C",
                "/src",
                ".",
            ],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr or "tar failed")
    except Exception as e:
        return {
            "backup_id": backup_id,
            "backup_name": f"{backup_id}.tar.gz",
            "backup_path": str(backup_file),
            "size_mb": 0,
            "size_bytes": 0,
            "status": "failed",
            "duration_seconds": round(time.time() - start, 1),
            "strategy": "manual",
            "collections_count": 0,
            "created_at": datetime.now().isoformat(),
            "error": str(e),
        }

    if backup_file.exists():
        size_bytes = backup_file.stat().st_size
    else:
        size_bytes = 0

    size_mb = round(size_bytes / (1024 * 1024), 2)

    result_dict: dict[str, Any] = {
        "backup_id": backup_id,
        "backup_name": f"{backup_id}.tar.gz",
        "backup_path": str(backup_file),
        "size_mb": size_mb,
        "size_bytes": size_bytes,
        "status": "completed",
        "duration_seconds": round(time.time() - start, 1),
        "strategy": "manual",
        "collections_count": 0,
        "created_at": datetime.now().isoformat(),
    }

    _save_meta(backup_dir, result_dict)
    _cleanup_old(backup_dir, retention)

    return result_dict


def restore_arangodb(backup_id: str, backup_path: str | None = None) -> dict[str, Any]:
    start = time.time()
    backup_dir = get_backup_dir(backup_path)
    backup_file = backup_dir / f"{backup_id}.tar.gz"

    if not backup_file.exists():
        return {
            "restore_id": f"{backup_id}_restore",
            "status": "failed",
            "duration_seconds": round(time.time() - start, 1),
            "collections_restored": [],
            "error": f"Backup file not found: {backup_file}",
        }

    try:
        get_docker_volume_path(ARANGO_VOLUME_NAME)
    except subprocess.CalledProcessError:
        return {
            "restore_id": f"{backup_id}_restore",
            "status": "failed",
            "duration_seconds": round(time.time() - start, 1),
            "collections_restored": [],
            "error": "ArangoDB volume not found",
        }

    try:
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{ARANGO_VOLUME_NAME}:/dst",
                "-v",
                f"{backup_dir}:/src:ro",
                "alpine",
                "sh",
                "-c",
                f"rm -rf /dst/* && tar xzf /src/{backup_id}.tar.gz -C /dst/",
            ],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr or "restore failed")
    except Exception as e:
        return {
            "restore_id": f"{backup_id}_restore",
            "status": "failed",
            "duration_seconds": round(time.time() - start, 1),
            "collections_restored": [],
            "error": str(e),
        }

    return {
        "restore_id": f"{backup_id}_restore",
        "status": "completed",
        "duration_seconds": round(time.time() - start, 1),
        "collections_restored": ["all"],
        "backup_file": str(backup_file),
    }


def delete_backup(backup_id: str, backup_path: str | None = None) -> dict[str, Any]:
    backup_dir = get_backup_dir(backup_path)
    backup_file = backup_dir / f"{backup_id}.tar.gz"
    meta_file = backup_dir / ".meta" / f"{backup_id}.json"

    deleted: list[str] = []
    errors: list[str] = []

    if backup_file.exists():
        backup_file.unlink()
        deleted.append(str(backup_file))

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
