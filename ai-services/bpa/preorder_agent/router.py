"""
@file        預購代理 — FastAPI Router
@description 提供預購品項查詢技能端點 query_preorder_items
              技能編號：SKL-2618-002
@lastUpdate  2026-04-30 01:50:00
@author      Daniel Chung
@version     1.0.0
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from bpa.preorder_agent.skills.query_preorder_items import execute

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Preorder Agent"])


class QueryPreorderItemsRequest(BaseModel):
    session_id: str = ""
    user_id: str = ""
    filter_term: str = ""


class QueryPreorderItemsResponse(BaseModel):
    success: bool
    data: list[dict[str, Any]]
    total_count: int
    error: str | None = None


@router.post("/skills/query_preorder_items", response_model=QueryPreorderItemsResponse)
async def skill_query_preorder_items(request: QueryPreorderItemsRequest) -> QueryPreorderItemsResponse:
    """技能端點：查詢預購可用之品項（品名、規格、庫存數量、單位）

    技能編號：SKL-2618-002
    用途：前置詢價或建立預購單時查詢可用品項
    """
    result = await execute(request.model_dump())
    return QueryPreorderItemsResponse(
        success=result.get("success", False),
        data=result.get("data", []),
        total_count=result.get("total_count", 0),
        error=result.get("error"),
    )