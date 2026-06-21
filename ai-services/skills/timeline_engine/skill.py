"""
@file        timeline_engine/skill.py
@description 客戶 Timeline 讀寫 Skill：查詢互動歷史、寫入新事件
@lastUpdate  2026-06-14
@author      Daniel Chung
@version     1.0.0

# Skill 規範

## 用途
提供統一的 Timeline 存取介面，支援：
- 查詢客戶 Timeline（支援 level=summary/full 權限過濾）
- 寫入新事件（含 ref_key 去重）
- 刪除事件

## 輸入
| 參數 | 類型 | 必填 | 說明 |
|------|------|------|------|
| action | enum | ✅ | query / write / delete |
| customer_id | string | ✅ | CRM 客戶 ID |
| level | enum | ❌ | summary / full（預設 full，僅 query 有效） |
| event | object | ❌ | write 時必填（見下方 Event 結構） |

## Event 結構
| 欄位 | 類型 | 必填 | 說明 |
|------|------|:----:|------|
| event_type | string | ✅ | quote_analysis / order_placed / shipment_delivered / ... |
| summary | string | ✅ | 活動摘要 |
| timestamp | string | ✅ | ISO 8601 |
| source | string | ❌ | erp / line_bot / internal_assistant / crm |
| detail_level | string | ❌ | summary / full |
| ref_key | string | ❌ | 用於去重的唯一識別 |
| metadata | object | ❌ | 附加資料 |
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

SUMMARY_LEVEL_FIELDS = {
    "summary": ["event_type", "summary", "timestamp", "source"],
    "full": None,
}

ALLOWED_EVENT_TYPES = [
    "quote_analysis", "inquiry_sent", "order_placed",
    "shipment_delivered", "return_processed", "credit_note_issued",
    "greeting_sent", "faq_answered", "visit_completed",
    "broadcast_sent", "business_card_received",
    "confidential_blocked", "image_shared",
]


async def execute(params: dict[str, Any]) -> dict[str, Any]:
    """Skill 統一進入點。

    Args:
        params: action, customer_id, level, event

    Returns:
        query → { events: [...] }
        write → { written: true, event_id: "..." }
        delete → { deleted: true }
    """
    action = params.get("action", "query")
    customer_id = params.get("customer_id", "")

    if not customer_id:
        return {"error": "customer_id is required"}

    if action == "query":
        return await _query(customer_id, params.get("level", "full"))
    elif action == "write":
        return await _write(customer_id, params.get("event", {}))
    elif action == "delete":
        return await _delete(customer_id, params.get("event_id", ""))
    else:
        return {"error": f"Unknown action: {action}"}


async def _query(customer_id: str, level: str = "full") -> dict[str, Any]:
    """查詢客戶 Timeline。"""
    from data_agent.config_reader import get_db

    db = get_db()
    docs = await db.aql_bind_vars(
        "FOR t IN customer_timelines FILTER t.customer_id == @cid LIMIT 1 RETURN t",
        [("cid", customer_id)],
    )

    if not docs:
        return {"events": []}

    events = docs[0].get("events", [])

    if level == "summary":
        allowed = SUMMARY_LEVEL_FIELDS["summary"]
        events = [
            {k: e[k] for k in allowed if k in e}
            for e in events
        ]

    return {"events": events}


async def _write(customer_id: str, event: dict[str, Any]) -> dict[str, Any]:
    """寫入新事件到 Timeline。"""
    from data_agent.config_reader import get_db

    event_type = event.get("event_type", "")
    if event_type not in ALLOWED_EVENT_TYPES:
        return {"error": f"Invalid event_type: {event_type}"}

    ref_key = event.get("ref_key", "")
    timestamp = event.get("timestamp", datetime.now(timezone.utc).isoformat())
    now = datetime.now(timezone.utc).isoformat()

    event_entry = {
        "event_id": event.get("event_id", f"{event_type}_{ref_key or now}"),
        "event_type": event_type,
        "summary": event.get("summary", ""),
        "timestamp": timestamp,
        "source": event.get("source", ""),
        "detail_level": event.get("detail_level", "full"),
        "ref_key": ref_key,
        "metadata": event.get("metadata", {}),
    }

    db = get_db()

    # 若有 ref_key，先檢查重複
    if ref_key:
        dup = await db.aql_bind_vars(
            """FOR t IN customer_timelines FILTER t.customer_id == @cid
               FOR e IN t.events FILTER e.ref_key == @rk LIMIT 1 RETURN 1""",
            [("cid", customer_id), ("rk", ref_key)],
        )
        if dup:
            return {"written": False, "event_id": None, "error": "duplicate ref_key"}

    # UPSERT
    await db.aql_bind_vars(
        """FOR t IN customer_timelines FILTER t.customer_id == @cid
           UPDATE t WITH { events: APPEND(t.events, [@event]), last_updated: @now } IN customer_timelines""",
        [("cid", customer_id), ("event", json.dumps(event_entry)), ("now", now)],
    )

    await db.aql_bind_vars(
        """LET exists = LENGTH(FOR t IN customer_timelines FILTER t.customer_id == @cid LIMIT 1 RETURN 1)
           FILTER exists == 0
           INSERT { _key: CONCAT("tl_", @cid), customer_id: @cid, events: [@event], last_updated: @now } INTO customer_timelines""",
        [("cid", customer_id), ("event", json.dumps(event_entry)), ("now", now)],
    )

    return {"written": True, "event_id": event_entry["event_id"]}


async def _delete(customer_id: str, event_id: str) -> dict[str, Any]:
    """從 Timeline 刪除指定事件。"""
    from data_agent.config_reader import get_db

    if not event_id:
        return {"error": "event_id is required"}

    db = get_db()
    await db.aql_bind_vars(
        """FOR t IN customer_timelines FILTER t.customer_id == @cid
           UPDATE t WITH { events: REMOVE_VALUE(t.events, 
               (FOR e IN t.events FILTER e.event_id == @eid LIMIT 1 RETURN e)[0]),
               last_updated: @now } IN customer_timelines""",
        [("cid", customer_id), ("eid", event_id), ("now", datetime.now(timezone.utc).isoformat())],
    )

    return {"deleted": True}
