from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/memory/session", tags=["Session Memory"])


class SessionMemoryUpdateRequest(BaseModel):
    title: Optional[str] = None
    current_state: Optional[str] = None
    task_spec: Optional[str] = None
    files_and_functions: Optional[list[str]] = None
    workflow: Optional[str] = None
    errors_and_corrections: Optional[list[str]] = None
    learnings: Optional[list[str]] = None
    key_results: Optional[list[str]] = None
    worklog: Optional[list[dict]] = None


from memory_agent.core import (
    get_session_memory,
    create_session_memory,
    update_session_memory,
    delete_session_memory,
    render_session_memory,
)


@router.get("/{session_id}")
def get_session_endpoint(session_id: str) -> dict:
    memory = get_session_memory(session_id)
    if not memory:
        return {"session_id": session_id, "exists": False}
    return {
        "session_id": memory.session_id,
        "exists": True,
        "rendered": render_session_memory(session_id),
        "title": memory.title,
        "updated_at": memory.updated_at.isoformat(),
    }


@router.post("/{session_id}")
def create_session_endpoint(session_id: str) -> dict:
    create_session_memory(session_id)
    return {"status": "created", "session_id": session_id}


@router.put("/{session_id}")
def update_session_endpoint(
    session_id: str, request: SessionMemoryUpdateRequest
) -> dict:
    update_session_memory(
        session_id,
        title=request.title,
        current_state=request.current_state,
        task_spec=request.task_spec,
        files_and_functions=request.files_and_functions,
        workflow=request.workflow,
        errors_and_corrections=request.errors_and_corrections,
        learnings=request.learnings,
        key_results=request.key_results,
        worklog=request.worklog,
    )
    return {"status": "updated", "session_id": session_id}


@router.delete("/{session_id}")
def delete_session_endpoint(session_id: str) -> dict:
    delete_session_memory(session_id)
    return {"status": "deleted", "session_id": session_id}
