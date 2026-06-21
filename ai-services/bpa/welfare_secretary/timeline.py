"""
@file        業務平台助手 — Timeline Engine
@description Timeline 讀寫模組，封裝 skills/timeline_engine 並擴充權限過濾
@lastUpdate  2026-06-19
@author      Sisyphus
@version     1.0.0
"""

import logging
from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Welfare Secretary - Timeline"])

# ── Pydantic models ──


class TimelineEvent(BaseModel):
    event_id: str = ""
    event_type: str
    summary: str
    timestamp: str = ""
    source: str = ""
    detail_level: str = "full"
    ref_key: str = ""
    metadata: dict = {}


class TimelineQueryRequest(BaseModel):
    customer_id: str
    level: str = "full"  # summary | full


class TimelineWriteRequest(BaseModel):
    customer_id: str
    event: TimelineEvent


class TimelineDeleteRequest(BaseModel):
    customer_id: str
    event_id: str


class TimelineResponse(BaseModel):
    success: bool = True
    events: list = []
    event_id: str | None = None
    error: str | None = None


# ── Skill wrappers ──


async def query_timeline(customer_id: str, level: str = "full") -> dict:
    """查詢客戶 Timeline，封裝 skills.timeline_engine。

    Args:
        customer_id: CRM 客戶 ID
        level: summary（僅摘要欄位）| full（完整事件）

    Returns:
        {"events": [...]} 或 {"error": "..."}
    """
    from skills.timeline_engine.skill import execute as tl_query

    return await tl_query({
        "action": "query",
        "customer_id": customer_id,
        "level": level,
    })


async def write_timeline_event(customer_id: str, event: dict) -> dict:
    """寫入新事件到 Timeline，含 ref_key 去重。

    Args:
        customer_id: CRM 客戶 ID
        event: 事件資料 (event_type, summary, timestamp, source, ref_key, metadata)

    Returns:
        {"written": True, "event_id": "..."} 或 {"error": "..."}
    """
    from skills.timeline_engine.skill import execute as tl_write

    return await tl_write({
        "action": "write",
        "customer_id": customer_id,
        "event": event,
    })


async def delete_timeline_event(customer_id: str, event_id: str) -> dict:
    """刪除 Timeline 中的指定事件。"""
    from skills.timeline_engine.skill import execute as tl_delete

    return await tl_delete({
        "action": "delete",
        "customer_id": customer_id,
        "event_id": event_id,
    })


# ── REST API ──


@router.post("/query", response_model=TimelineResponse)
async def api_query_timeline(req: TimelineQueryRequest) -> TimelineResponse:
    """查詢客戶 Timeline（支援 level=summary/full 權限過濾）"""
    result = await query_timeline(req.customer_id, req.level)
    if "error" in result:
        return TimelineResponse(success=False, error=result["error"])
    return TimelineResponse(events=result.get("events", []))


@router.post("/write", response_model=TimelineResponse)
async def api_write_timeline(req: TimelineWriteRequest) -> TimelineResponse:
    """寫入新事件到 Timeline"""
    result = await write_timeline_event(req.customer_id, req.event.model_dump())
    if "error" in result:
        return TimelineResponse(success=False, error=result["error"])
    return TimelineResponse(event_id=result.get("event_id"))


@router.post("/delete", response_model=TimelineResponse)
async def api_delete_timeline(req: TimelineDeleteRequest) -> TimelineResponse:
    """刪除 Timeline 事件"""
    result = await delete_timeline_event(req.customer_id, req.event_id)
    if "error" in result:
        return TimelineResponse(success=False, error=result["error"])
    return TimelineResponse(success=True)
