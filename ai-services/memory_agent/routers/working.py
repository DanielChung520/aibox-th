from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

router = APIRouter(prefix="/memory/working", tags=["Working Memory"])

from memory_agent.core import (
    WorkingMemory,
    get_working_memory,
    set_working_memory,
    clear_working_memory,
)


class WorkingMemoryUpdateRequest(BaseModel):
    task_id: str
    session_id: str
    task_progress: str = ""
    offsets: Optional[dict[str, int]] = None
    machine_states: Optional[dict[str, dict]] = None


@router.get("/{session_id}/{task_id}")
def get_working_endpoint(session_id: str, task_id: str) -> dict:
    memory = get_working_memory(task_id, session_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Working memory not found")
    return {
        "task_id": memory.task_id,
        "session_id": memory.session_id,
        "task_progress": memory.task_progress,
        "offsets": memory.offsets,
        "machine_states": memory.machine_states,
        "last_updated": memory.last_updated.isoformat(),
    }


@router.put("/")
def set_working_endpoint(request: WorkingMemoryUpdateRequest) -> dict:
    memory = WorkingMemory(
        task_id=request.task_id,
        session_id=request.session_id,
        task_progress=request.task_progress,
        offsets=request.offsets or {},
        machine_states=request.machine_states or {},
        last_updated=datetime.now(),
    )
    set_working_memory(memory)
    return {
        "status": "updated",
        "task_id": request.task_id,
        "session_id": request.session_id,
    }


@router.delete("/{session_id}/{task_id}")
def clear_working_endpoint(session_id: str, task_id: str) -> dict:
    clear_working_memory(task_id, session_id)
    return {"status": "deleted", "task_id": task_id, "session_id": session_id}
