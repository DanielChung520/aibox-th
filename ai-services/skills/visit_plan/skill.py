"""
@file        visit_plan/skill.py
@description 行程安排 Skill：記錄拜訪日期/地點/客戶 → 地圖估程 → 提醒
@lastUpdate  2026-06-20
@author      Sisyphus
@version     1.0.0

# Skill 規範
## 用途
建立業務拜訪行程，含客戶資訊、地點、估程與提醒設定（Phase 2 實作）。
"""

from __future__ import annotations
import logging
from typing import Any

logger = logging.getLogger(__name__)


async def execute(params: dict[str, Any]) -> dict[str, Any]:
    """建立拜訪行程（Phase 2 實作，目前回傳 stub）"""
    customer_id = params.get("customer_id", "")
    customer_name = params.get("customer_name", "")
    visit_date = params.get("visit_date", "")
    location = params.get("location", "")

    if not customer_id or not visit_date:
        return {"error": "customer_id 與 visit_date 為必填"}

    # TODO: Phase 2 實作
    # 1. 寫入 visit_plans 集合
    # 2. 呼叫 Google Maps Distance Matrix API 估程
    # 3. 設定提醒

    logger.info(f"[VisitPlan] Stub: visit for {customer_name} on {visit_date} at {location}")

    return {
        "visit_id": "",
        "estimated_travel_min": 0,
        "status": "planned",
        "message": "行程功能開發中（Phase 2）",
    }
