"""
@file        business_notification/skill.py
@description 業務通知 Skill：客戶觸發機密拒答時，LINE 通知業務人員跟進
@lastUpdate  2026-06-20
@author      Sisyphus
@version     1.0.0

# Skill 規範
## 用途
當客戶端攔截到 L3/L4 機密問題時，非同步 LINE 通知對應業務人員。
"""

from __future__ import annotations
import logging
from typing import Any

logger = logging.getLogger(__name__)

NOTIFICATION_TEMPLATE = (
    "🔔 [業務平台助手通知]\n"
    "客戶 {customer_name} 剛剛詢問了「{query_type}」，\n"
    "已依權限設定婉轉回覆。如需跟進請與客戶聯繫。"
)


async def execute(params: dict[str, Any]) -> dict[str, Any]:
    customer_name = params.get("customer_name", "未知客戶")
    query_type = params.get("query_type", "機密資訊")
    business_line_id = params.get("business_line_id", "")

    if not business_line_id:
        logger.warning("[BusinessNotification] No business LINE ID provided")
        return {"sent": False, "notification_text": ""}

    notification_text = NOTIFICATION_TEMPLATE.format(
        customer_name=customer_name,
        query_type=query_type,
    )

    try:
        from skills.push_engine.skill import execute as push

        result = await push({
            "action": "execute_task",
            "task": {
                "target_users": [{"line_id": business_line_id}],
                "message": {"type": "text", "text": notification_text},
            },
        })
        sent = result.get("success", False)
    except Exception as e:
        logger.warning(f"[BusinessNotification] Push failed: {e}")
        sent = False

    return {
        "sent": sent,
        "notification_text": notification_text,
    }
