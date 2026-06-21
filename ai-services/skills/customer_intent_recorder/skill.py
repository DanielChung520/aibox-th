"""
@file        customer_intent_recorder/skill.py
@description 客戶意圖記錄 Skill：對於不在正面表列的客戶訊息，分析意圖、記錄、轉告業務
@lastUpdate  2026-06-20
@author      Sisyphus
@version     1.0.0

# Skill 規範

## 用途
分析客戶未匹配意圖的訊息，推測其意圖與業務關鍵詞，記錄到 customer_timelines，
並決定是否需要通知綁定業務。

## 輸入
| 參數 | 類型 | 必填 | 說明 |
|------|------|------|------|
| message | string | ✅ | 客戶原始訊息 |
| business_user_key | string | ❌ | 綁定的業務 ID |
| channel_key | string | ❌ | 管道識別碼 |
| customer_name | string | ❌ | 客戶名稱 |
| session_id | string | ❌ | 對話 ID |

## 輸出
| 屬性 | 類型 | 說明 |
|------|------|------|
| reply | string | 回覆客戶的文字 |
| should_notify | bool | 是否需通知業務 |
| analysis | dict | {inferred_intent, business_keywords, urgency} |
| recorded | bool | 是否已記錄 |
"""

from __future__ import annotations

import json
import logging
import base64
import httpx
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

ANALYSIS_PROMPT = """你是一個業務助理的分析模組。請分析以下客戶訊息，推測其意圖與業務相關性。

客戶名稱：{customer_name}
訊息：{message}

請以 JSON 格式回傳分析結果：
{{
  "inferred_intent": "推測的客戶意圖（一句話）",
  "business_keywords": ["偵測到的業務關鍵詞"],
  "urgency": "low | medium | high",
  "is_business_related": true | false,
  "summary": "給業務看的摘要（50字內）"
}}

只回傳 JSON，不要其他文字。"""


async def execute(params: dict[str, Any]) -> dict[str, Any]:
    """分析客戶意圖、記錄、決定是否轉告業務。"""
    message = params.get("message", "")
    business_user_key = params.get("business_user_key", "")
    channel_key = params.get("channel_key", "")
    customer_name = params.get("customer_name", "客戶")
    session_id = params.get("session_id", "")

    # LLM 分析意圖
    analysis = await _analyze_intent(message, customer_name)

    # 記錄到 customer_timelines
    recorded = await _record_intent(
        business_user_key=business_user_key,
        channel_key=channel_key,
        session_id=session_id,
        customer_name=customer_name,
        message=message,
        analysis=analysis,
    )

    # 決定是否通知業務：有綁定業務 + 與業務相關 或 高急迫性
    should_notify = bool(business_user_key) and (
        analysis.get("is_business_related", False) or analysis.get("urgency") == "high"
    )

    if should_notify:
        reply = "感謝您的訊息，我已經轉達給負責的業務專員，他將儘快與您聯繫。"
    else:
        reply = "感謝您的訊息，我已記錄下來。"

    return {
        "reply": reply,
        "should_notify": should_notify,
        "analysis": analysis,
        "recorded": recorded,
    }


async def _analyze_intent(message: str, customer_name: str) -> dict:
    """用 LLM 推測客戶意圖。"""
    from shared.llm_resolver import resolve_and_call

    prompt = ANALYSIS_PROMPT.format(customer_name=customer_name, message=message)
    result = await resolve_and_call(
        messages=[
            {"role": "system", "content": "你是一個精準的業務意圖分析器。請嚴格按照 JSON 格式回傳。"},
            {"role": "user", "content": prompt},
        ],
        model="ollama:gemma4:31b",
        temperature=0.1,
        max_tokens=256,
    )
    content = result.get("content", "{}")
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        logger.warning(f"[IntentRecorder] LLM parse failed: {content[:200]}")
        return {
            "inferred_intent": "無法分析",
            "business_keywords": [],
            "urgency": "low",
            "is_business_related": False,
            "summary": message[:50],
        }


async def _record_intent(
    business_user_key: str,
    channel_key: str,
    session_id: str,
    customer_name: str,
    message: str,
    analysis: dict,
) -> bool:
    """記錄客戶意圖到 customer_timelines。"""
    from bpa.welfare_secretary.config import ARANGO_URL, ARANGO_DB, ARANGO_USER, ARANGO_PASSWORD

    auth_cred = f"{ARANGO_USER}:{ARANGO_PASSWORD}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {base64.b64encode(auth_cred.encode()).decode()}",
    }
    doc = {
        "customer_id": f"contact_{channel_key}" if channel_key else f"session_{session_id}",
        "event_type": "customer_intent_unmatched",
        "summary": analysis.get("summary", message[:50]),
        "detail_level": "full",
        "source": "customer_assistant",
        "business_user_key": business_user_key,
        "metadata": {
            "channel_key": channel_key,
            "session_id": session_id,
            "customer_name": customer_name,
            "full_message": message,
            "inferred_intent": analysis.get("inferred_intent"),
            "business_keywords": analysis.get("business_keywords", []),
            "urgency": analysis.get("urgency", "low"),
            "is_business_related": analysis.get("is_business_related", False),
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
        logger.warning(f"[IntentRecorder] Record failed: {e}")
        return False
