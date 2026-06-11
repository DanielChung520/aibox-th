"""
Consolidation module - offline memory organization.
"""

import os
import time
from datetime import datetime, timedelta
from pathlib import Path

from memory_agent.core.models import (
    ConsolidationResult,
    ConsolidationStats,
    Memory,
    MemoryType,
)
from memory_agent.core.storage import (
    get_memory_dir,
    parse_memory_file,
)


LOCK_FILE = ".consolidation.lock"
MIN_INTERVAL_HOURS = 24
MIN_NEW_MEMORIES = 5
MAX_LOCK_AGE_SECONDS = 30 * 60


def get_lock_path() -> Path:
    return get_memory_dir() / LOCK_FILE


def acquire_consolidation_lock() -> bool:
    lock_path = get_lock_path()
    if lock_path.exists():
        try:
            content = lock_path.read_text(encoding="utf-8")
            pid_str = content.strip()
            if pid_str:
                pass
            lock_mtime = datetime.fromtimestamp(lock_path.stat().st_mtime)
            if datetime.now() - lock_mtime > timedelta(seconds=MAX_LOCK_AGE_SECONDS):
                lock_path.unlink()
            else:
                return False
        except Exception:
            lock_path.unlink()
    try:
        lock_path.write_text(str(os.getpid()), encoding="utf-8")
        return True
    except Exception:
        return False


def release_consolidation_lock() -> None:
    lock_path = get_lock_path()
    if lock_path.exists():
        try:
            content = lock_path.read_text(encoding="utf-8")
            if content.strip() == str(os.getpid()):
                lock_path.unlink()
        except Exception:
            pass


def should_run_consolidation() -> bool:
    lock_path = get_lock_path()
    if not lock_path.exists():
        return True
    try:
        lock_mtime = datetime.fromtimestamp(lock_path.stat().st_mtime)
        if datetime.now() - lock_mtime > timedelta(hours=MIN_INTERVAL_HOURS):
            return True
        return False
    except Exception:
        return True


def count_new_memories(since_hours: int = 24) -> int:
    base_dir = get_memory_dir()
    cutoff = datetime.now() - timedelta(hours=since_hours)
    count = 0
    for memory_type in MemoryType:
        type_dir = base_dir / memory_type.value
        if type_dir.exists():
            for file_path in type_dir.glob("*.md"):
                try:
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if mtime > cutoff:
                        count += 1
                except Exception:
                    pass
    return count


def scan_for_duplicates(memories: list[Memory]) -> dict[str, list[Memory]]:
    duplicates: dict[str, list[Memory]] = {}
    name_map: dict[str, list[Memory]] = {}
    for memory in memories:
        key = memory.name.lower().strip()
        if key not in name_map:
            name_map[key] = []
        name_map[key].append(memory)
    for name, memory_list in name_map.items():
        if len(memory_list) > 1:
            duplicates[name] = memory_list
    return duplicates


def consolidate_memories(force: bool = False) -> ConsolidationResult:
    start_time = time.time()
    stats = ConsolidationStats()
    errors: list[str] = []
    if not force and not should_run_consolidation():
        return ConsolidationResult(
            success=True,
            stats=stats,
            errors=["Consolidation not needed yet"],
        )
    if not acquire_consolidation_lock():
        return ConsolidationResult(
            success=False,
            stats=stats,
            errors=["Could not acquire lock"],
        )
    try:
        base_dir = get_memory_dir()
        all_memories: list[Memory] = []
        for memory_type in MemoryType:
            type_dir = base_dir / memory_type.value
            if type_dir.exists():
                for file_path in type_dir.glob("*.md"):
                    memory = parse_memory_file(file_path)
                    if memory:
                        all_memories.append(memory)
                        stats.memories_scanned += 1
        duplicates = scan_for_duplicates(all_memories)
        for _name, memory_list in duplicates.items():
            if len(memory_list) > 1:
                stats.memories_merged += 1
        stats.duration_ms = int((time.time() - start_time) * 1000)
        return ConsolidationResult(
            success=True,
            stats=stats,
            errors=errors,
        )
    except Exception as e:
        errors.append(str(e))
        return ConsolidationResult(
            success=False,
            stats=stats,
            errors=errors,
        )
    finally:
        release_consolidation_lock()
