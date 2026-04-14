from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/memory", tags=["Memory"])

from memory_agent.core import (
    MEMORY_TYPES,
    MemoryCreate,
    create_memory,
    get_memory,
    get_all_memories,
    update_memory,
    delete_memory,
)


class RecallRequest(BaseModel):
    query: str
    top_k: int = 5
    project_id: Optional[str] = None


class ContentCheckRequest(BaseModel):
    content: str


@router.get("/types")
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


@router.get("/")
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


@router.get("/{memory_id}")
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


@router.post("/")
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


@router.put("/{memory_id}")
def update_memory_endpoint(memory_id: str, updates: dict) -> dict:
    try:
        memory = update_memory(memory_id, updates)
        return {"status": "updated", "memory_id": memory.memory_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{memory_id}")
def delete_memory_endpoint(memory_id: str) -> dict:
    try:
        delete_memory(memory_id)
        return {"status": "deleted", "memory_id": memory_id}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/recall")
async def recall_memories_endpoint(request: RecallRequest) -> dict:
    from memory_agent.core import recall_memories

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


@router.post("/check-content")
def check_content_endpoint(request: ContentCheckRequest) -> dict:
    from memory_agent.core import should_save_content, scan_content

    can_save = should_save_content(request.content)
    detection = scan_content(request.content)
    return {
        "can_save": can_save,
        "has_secrets": detection.has_secrets,
        "detected_patterns": detection.detected_patterns,
    }
