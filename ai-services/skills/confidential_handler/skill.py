"""
@file        confidential_handler/skill.py
@description 機密資訊查詢處理 Skill：依提問者身分分流 — 業務本人調用 subagent，其餘婉拒+記錄+通知
@lastUpdate  2026-06-20
@author      Sisyphus
@version     1.0.0

# Skill 規範

## 用途
接收機密資訊查詢（報價/金額/合約等），依 role 決定處理方式：
- role=業務員 → route_to_subagent（調用 Data Agent）
- role≠業務員 → polite_refuse + 記錄查詢內容 + 通知業務

## 輸入
| 參數 | 類型 | 必填 | 說明 |
|------|------|------|------|
| message | string | ✅ | 原始查詢內容 |
| business_user_key | string | ❌ | 管道綁定的業務 ID |
| role | string | ❌ | 提問者角色（業務員/客戶/空字串） |
| channel_key | string | ❌ | 管道識別碼 |
| session_id | string | ❌ | 對話 ID |
| customer_name | string | ❌ | 提問者名稱 |

## 輸出
| 屬性 | 類型 | 說明 |
|------|------|------|
| action | string | route_to_subagent | polite_refuse |
| reply | string | 回覆文字 |
| should_notify | bool | 是否需要通知業務 |
| should_record | bool | 是否需要記錄查詢 |
| query_type | string | 查詢類型描述 |
"""

from __future__ import annotations

import logging
import base64
import httpx
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


async def execute(params: dict[str, Any]) -> dict[str, Any]:
    """依 role 分流：業務員→subagent，其他→婉拒+記錄+通知。"""
    message = params.get("message", "")
    business_user_key = params.get("business_user_key", "")
    role = params.get("role", "")
    channel_key = params.get("channel_key", "")
    session_id = params.get("session_id", "")
    customer_name = params.get("customer_name", "未知")

    if role == "業務員":
        return {
            "action": "route_to_subagent",
            "reply": "",
            "should_notify": False,
            "should_record": False,
            "query_type": "機密資訊（業務本人查詢）",
        }

    if bool(business_user_key):
        reply = "感謝您的詢問。關於價格、合約等詳細資訊，我已轉達給負責的業務專員，他將儘快與您聯繫說明。"
    else:
        reply = "您的詢問我收到了，我會轉達主管，請主管盡快回應您。"

    recorded = await _record_query(
        business_user_key=business_user_key,
        channel_key=channel_key,
        session_id=session_id,
        customer_name=customer_name,
        message=message,
    )

    return {
        "action": "polite_refuse",
        "reply": reply,
        "should_notify": bool(business_user_key),
        "should_record": recorded,
        "query_type": "報價金額/合約條款",
    }


async def _record_query(
    business_user_key: str,
    channel_key: str,
    session_id: str,
    customer_name: str,
    message: str,
) -> bool:
    """將機密查詢記錄寫入 customer_timelines（方便業務後續跟進）。"""
    from bpa.welfare_secretary.config import ARANGO_URL, ARANGO_DB, ARANGO_USER, ARANGO_PASSWORD

    auth_cred = f"{ARANGO_USER}:{ARANGO_PASSWORD}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {base64.b64encode(auth_cred.encode()).decode()}",
    }
    doc = {
        "customer_id": f"contact_{channel_key}" if channel_key else f"session_{session_id}",
        "event_type": "confidential_query_blocked",
        "summary": f"客戶({customer_name})詢問機密資訊：{message[:80]}",
        "detail_level": "summary",
        "source": "customer_assistant",
        "business_user_key": business_user_key,
        "metadata": {
            "channel_key": channel_key,
            "session_id": session_id,
            "customer_name": customer_name,
            "full_message": message,
        },
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/document/customer_timelines",
                json=doc,
                headers=headers,
            )
            return resp.status_code in (200, 201, 202)
    except Exception as e:
        logger.warning(f"[ConfidentialHandler] Record failed: {e}")
        return False
