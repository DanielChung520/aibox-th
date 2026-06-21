"""
@file        push_engine/skill.py
@description 排程推播 Skill：LINE Push 逐筆發送取代 Broadcast
@lastUpdate  2026-06-14
@author      Daniel Chung
@version     1.0.0

# Skill 規範

## 用途
以 LINE Push API 逐筆遍歷客戶，取代 Broadcast 限制。
支援個人化模板、排程發送、送達追蹤。

完整規格：.docs/Spec/系統開發/04-排程推播系統.md
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def execute(params: dict[str, Any]) -> dict[str, Any]:
    """Skill 統一進入點。"""
    action = params.get("action", "create_task")
    task = params.get("task", {})

    if action == "create_task":
        return await _create_task(task)
    elif action == "preview":
        return await _preview(task)
    elif action == "execute_task":
        return await _execute_task(task.get("task_key", ""))
    elif action == "cancel_task":
        return await _cancel_task(task.get("task_key", ""))
    else:
        return {"error": f"Unknown action: {action}"}


async def _create_task(task: dict) -> dict[str, Any]:
    """建立推播任務。"""
    from data_agent.config_reader import get_db
    from datetime import datetime, timezone
    import uuid

    task_key = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    doc = {
        "_key": task_key,
        "title": task.get("title", ""),
        "status": "scheduled",
        "task_type": task.get("schedule_type", "one_time"),
        "scheduled_at": task.get("scheduled_at", now),
        "schedule_cron": task.get("schedule_cron", ""),
        "target_query": task.get("target_query", {}),
        "content_template": task.get("content_template", {}),
        "processed_count": 0,
        "success_count": 0,
        "fail_count": 0,
        "last_index": 0,
        "created_by": task.get("created_by", "system"),
        "created_at": now,
        "updated_at": now,
    }

    db = get_db()
    col = await db.collection("broadcast_tasks")
    await col.create_document(doc)

    return {"task_key": task_key, "status": "created"}


async def _preview(task: dict) -> dict[str, Any]:
    """預覽個人化結果（抽樣 3 筆）。"""
    from data_agent.config_reader import get_db

    target_query = task.get("target_query", {})
    content_template = task.get("content_template", {})
    text_template = content_template.get("text", "")

    db = get_db()
    samples = await db.aql_bind_vars(
        "FOR c IN crm_contacts FILTER c.status == 'active' LIMIT 3 RETURN {customer_name: c.name, line_user_id: c.line_user_id}",
        [],
    )

    previews = []
    for s in samples:
        rendered = text_template.replace("{{customer_name}}", s.get("customer_name", ""))
        previews.append({
            "customer_name": s.get("customer_name", ""),
            "rendered": rendered,
        })

    return {"preview_samples": previews, "sample_count": len(previews)}


async def _execute_task(task_key: str) -> dict[str, Any]:
    """執行推播任務（逐筆發送）。"""
    return {
        "task_key": task_key,
        "status": "not_implemented",
        "message": "Full execution implemented in push_engine.py",
    }


async def _cancel_task(task_key: str) -> dict[str, Any]:
    """取消推播任務。"""
    from data_agent.config_reader import get_db

    db = get_db()
    col = await db.collection("broadcast_tasks")
    await col.update_document(task_key, {"status": "cancelled"})

    return {"task_key": task_key, "status": "cancelled"}
