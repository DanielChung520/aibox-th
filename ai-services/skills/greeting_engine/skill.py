"""
@file        greeting_engine/skill.py
@description 個人化問候生成 Skill：CRM 尊稱查詢 → LLM 生成問候
@lastUpdate  2026-06-14
@author      Daniel Chung
@version     1.0.0

# Skill 規範

## 用途
根據 CRM 客戶資料（職稱、姓名）決定尊稱，LLM 生成個人化問候。

## 輸入
| 參數 | 類型 | 必填 | 說明 |
|------|------|------|------|
| customer_id | string | ❌ | CRM 客戶 ID（與 customer_name 二選一） |
| customer_name | string | ❌ | 客戶名稱（直接傳入） |
| greeting_type | enum | ✅ | morning / holiday / birthday / event |
| extra_context | string | ❌ | 額外資訊（如節日名稱） |

## 輸出
| 屬性 | 類型 | 說明 |
|------|------|------|
| greeting_text | string | 生成的問候文字 |
| honorific | string | 使用的尊稱 |
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_HONORIFIC = "尊敬的客戶"

HONORIFIC_MAP = {
    "董事長": "董事長",
    "總經理": "總經理",
    "經理": "經理",
    "副理": "副理",
    "主任": "主任",
    "組長": "組長",
    "教授": "教授",
    "博士": "博士",
    "先生": "先生",
    "小姐": "小姐",
    "女士": "女士",
}


async def execute(params: dict[str, Any]) -> dict[str, Any]:
    """生成個人化問候。"""
    customer_id = params.get("customer_id", "")
    customer_name = params.get("customer_name", "")
    greeting_type = params.get("greeting_type", "morning")
    extra_context = params.get("extra_context", "")

    # 查詢 CRM 取得客戶名稱與職稱
    title = None
    if customer_id and not customer_name:
        name, title = await _lookup_customer(customer_id)
        customer_name = name or "客戶"

    # 決定尊稱
    honorific = _resolve_honorific(title, customer_name)

    # LLM 生成問候
    greeting = await _generate_greeting(customer_name, honorific, greeting_type, extra_context)

    # 寫入客戶 timeline
    try:
        from skills.timeline_engine.skill import execute as tl_write
        await tl_write({
            "action": "write",
            "customer_id": customer_id or customer_name,
            "event": {
                "event_type": "greeting_sent",
                "summary": f"{greeting_type}問候：{greeting[:60]}",
                "source": "internal_assistant",
                "detail_level": "summary",
            }
        })
    except Exception:
        pass  # timeline 寫入失敗不影響問候本身

    return {
        "greeting_text": greeting,
        "honorific": honorific,
    }


async def _lookup_customer(customer_id: str) -> tuple[str | None, str | None]:
    """從 CRM 查詢客戶名稱與職稱。"""
    from data_agent.config_reader import get_db

    db = get_db()
    docs = await db.aql_bind_vars(
        "FOR c IN crm_contacts FILTER c._key == @key LIMIT 1 RETURN {name: c.name, title: c.title}",
        [("key", customer_id)],
    )
    if docs:
        return docs[0].get("name"), docs[0].get("title")
    return None, None


def _resolve_honorific(title: str | None, name: str | None) -> str:
    """根據職稱決定尊稱。"""
    if title and title in HONORIFIC_MAP:
        return HONORIFIC_MAP[title]
    if title and "長" in title:
        return title
    return DEFAULT_HONORIFIC


async def _generate_greeting(
    name: str | None,
    honorific: str,
    greeting_type: str,
    extra_context: str,
) -> str:
    """LLM 生成個人化問候。"""
    from shared.llm_resolver import resolve_and_call

    type_labels = {
        "morning": "早安",
        "holiday": "節日祝福",
        "birthday": "生日祝福",
        "event": "活動通知",
    }
    label = type_labels.get(greeting_type, "問候")

    context = f" ({extra_context})" if extra_context else ""
    full_name = f"{honorific} {name}" if name and name != "客戶" else honorific

    prompt = f"""你是一個業務助理，請以{full_name}的名義，
生成一個{label}{context}。語氣溫暖禮貌，不涉及任何業務資訊。直接輸出回覆內容。"""

    result = await resolve_and_call(
        messages=[{"role": "user", "content": prompt}],
        model="ollama:gemma4:31b",
        temperature=0.7,
        max_tokens=256,
    )

    return result.get("content", f"{full_name}，祝您有美好的一天！")
