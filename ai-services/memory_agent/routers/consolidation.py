from fastapi import APIRouter

router = APIRouter(prefix="/memory/consolidate", tags=["Memory Consolidation"])

from memory_agent.core import (
    consolidate_memories,
    should_run_consolidation,
    count_new_memories,
)


@router.post("/")
def consolidate_endpoint(force: bool = False) -> dict:
    result = consolidate_memories(force)
    return {
        "success": result.success,
        "stats": {
            "memories_scanned": result.stats.memories_scanned,
            "memories_merged": result.stats.memories_merged,
            "memories_pruned": result.stats.memories_pruned,
            "duration_ms": result.stats.duration_ms,
        },
        "errors": result.errors,
    }


@router.get("/status")
def consolidate_status_endpoint() -> dict:
    can_run = should_run_consolidation()
    new_count = count_new_memories()
    return {
        "can_run": can_run,
        "new_memories_count": new_count,
        "min_interval_hours": 24,
    }
