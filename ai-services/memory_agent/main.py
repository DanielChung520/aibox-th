"""
Memory Agent Service - AI-Augmented Memory System

Provides persistent, long-term memory capabilities for AIBox AI system.
Port: 8008

# Last Update: 2026-04-06 11:20:10
# Author: Daniel Chung
# Version: 1.0.0
"""

import os
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from memory_agent.core import (
    MEMORY_TYPES,
    MemoryCreate,
    WorkingMemory,
    create_memory,
    get_memory,
    get_all_memories,
    update_memory,
    delete_memory,
    read_index,
    should_save_content,
    scan_content,
    recall_memories,
    get_session_memory,
    create_session_memory,
    update_session_memory,
    delete_session_memory,
    render_session_memory,
    get_working_memory,
    set_working_memory,
    clear_working_memory,
    consolidate_memories,
    should_run_consolidation,
    count_new_memories,
    generate_system_prompt,
)


app = FastAPI(
    title="AIBox Memory Agent Service",
    description="AI-Augmented Memory System for persistent, long-term memory capabilities.",
    version="1.0.0",
)

ALLOWED_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:1420,http://localhost:6500",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MEMORY_DIR = os.getenv("AIBOX_MEMORY_DIR", "~/.aibox/memory")


class RecallRequest(BaseModel):
    query: str
    top_k: int = 5
    project_id: Optional[str] = None


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


class WorkingMemoryUpdateRequest(BaseModel):
    task_id: str
    session_id: str
    task_progress: str = ""
    offsets: Optional[dict[str, int]] = None
    machine_states: Optional[dict[str, dict]] = None


class ContentCheckRequest(BaseModel):
    content: str


@app.get("/")
def root() -> dict:
    return {
        "service": "memory_agent",
        "description": "AI-Augmented Memory System",
        "version": "1.0.0",
        "port": "8008",
        "status": "running",
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "memory_agent"}


@app.get("/memory/types")
def list_memory_types() -> dict:
    return {
        "types": list(MEMORY_TYPES),
        "descriptions": {
            "user": "用戶畫像、角色、目標、知識背景",
            "feedback": "工作方式指導（糾正和確認）",
            "project": "項目進展、目標、截止日期",
            "reference": "外部系統指針",
        },
    }


@app.get("/memory")
def list_memories(project_id: Optional[str] = None) -> dict:
    memories = get_all_memories(project_id)
    return {
        "memories": [
            {
                "memory_id": m.memory_id,
                "name": m.name,
                "type": m.type.value,
                "description": m.description,
                "scope": m.scope,
                "created_at": m.created_at.isoformat(),
                "updated_at": m.updated_at.isoformat(),
            }
            for m in memories
        ],
        "count": len(memories),
    }


@app.get("/memory/{memory_id}")
def get_memory_by_id(memory_id: str) -> dict:
    try:
        memory = get_memory(memory_id)
        return {
            "memory_id": memory.memory_id,
            "name": memory.name,
            "type": memory.type.value,
            "description": memory.description,
            "content": memory.content,
            "scope": memory.scope,
            "created_at": memory.created_at.isoformat(),
            "updated_at": memory.updated_at.isoformat(),
        }
    except Exception:
        raise HTTPException(status_code=404, detail=f"Memory not found: {memory_id}")


@app.post("/memory")
def create_memory_endpoint(memory_data: MemoryCreate) -> dict:
    try:
        memory = create_memory(memory_data)
        return {
            "status": "created",
            "memory_id": memory.memory_id,
            "type": memory.type.value,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/memory/{memory_id}")
def update_memory_endpoint(memory_id: str, updates: dict) -> dict:
    try:
        memory = update_memory(memory_id, updates)
        return {
            "status": "updated",
            "memory_id": memory.memory_id,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/memory/{memory_id}")
def delete_memory_endpoint(memory_id: str) -> dict:
    try:
        delete_memory(memory_id)
        return {"status": "deleted", "memory_id": memory_id}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/memory/recall")
async def recall_memories_endpoint(request: RecallRequest) -> dict:
    memories = get_all_memories(request.project_id)
    results = await recall_memories(request.query, memories, request.top_k)
    return {
        "query": request.query,
        "results": [
            {
                "memory_id": r.memory.memory_id,
                "name": r.memory.name,
                "type": r.memory.type.value,
                "description": r.memory.description,
                "content": r.memory.content,
                "relevance_score": r.relevance_score,
                "freshness": r.freshness,
                "needs_verification": r.needs_verification,
            }
            for r in results
        ],
        "count": len(results),
    }


@app.post("/memory/check-content")
def check_content_endpoint(request: ContentCheckRequest) -> dict:
    can_save = should_save_content(request.content)
    detection = scan_content(request.content)
    return {
        "can_save": can_save,
        "has_secrets": detection.has_secrets,
        "detected_patterns": detection.detected_patterns,
    }


@app.get("/memory/index")
def get_memory_index(project_id: Optional[str] = None) -> dict:
    from memory_agent.core.storage import ensure_memory_dir

    if project_id:
        base_dir = ensure_memory_dir(project_id)
    else:
        base_dir = ensure_memory_dir()
    index = read_index(base_dir)
    return {
        "total_lines": index.total_lines,
        "last_updated": index.last_updated.isoformat(),
        "entries": [
            {
                "memory_id": e.memory_id,
                "filename": e.filename,
                "description": e.description,
                "type": e.type.value,
                "line": e.line,
            }
            for e in index.entries
        ],
    }


@app.get("/memory/system-prompt")
async def get_system_prompt() -> dict:
    prompt = await generate_system_prompt(MEMORY_DIR)
    return {"prompt": prompt}


@app.get("/memory/session/{session_id}")
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


@app.post("/memory/session/{session_id}")
def create_session_endpoint(session_id: str) -> dict:
    create_session_memory(session_id)
    return {"status": "created", "session_id": session_id}


@app.put("/memory/session/{session_id}")
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


@app.delete("/memory/session/{session_id}")
def delete_session_endpoint(session_id: str) -> dict:
    delete_session_memory(session_id)
    return {"status": "deleted", "session_id": session_id}


@app.get("/memory/working/{session_id}/{task_id}")
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


@app.put("/memory/working")
def set_working_endpoint(request: WorkingMemoryUpdateRequest) -> dict:
    from datetime import datetime

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


@app.delete("/memory/working/{session_id}/{task_id}")
def clear_working_endpoint(session_id: str, task_id: str) -> dict:
    clear_working_memory(task_id, session_id)
    return {"status": "deleted", "task_id": task_id, "session_id": session_id}


@app.post("/memory/consolidate")
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


@app.get("/memory/consolidate/status")
def consolidate_status_endpoint() -> dict:
    can_run = should_run_consolidation()
    new_count = count_new_memories()
    return {
        "can_run": can_run,
        "new_memories_count": new_count,
        "min_interval_hours": 24,
    }
