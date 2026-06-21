"""
@file        image_processor/skill.py
@description 圖片分類與處理 Skill：問候回覆生成、名片 OCR、其他圖片摘要
@lastUpdate  2026-06-14
@author      Daniel Chung
@version     1.0.0

# Skill 規範

## 用途
接收圖片（base64），自動分類並執行對應處理：
- greeting → LLM 生成個人化問候回覆
- business_card → OCR 提取結構化資訊
- other → 圖片摘要

## 輸入
| 參數 | 類型 | 必填 | 說明 |
|------|------|------|------|
| image_base64 | string | ✅ | base64 編碼圖片 |
| mode | enum | ❌ | auto / greeting / business_card / other |
| customer_name | string | ❌ | 客戶名稱（問候用） |

## 輸出
| 屬性 | 類型 | 說明 |
|------|------|------|
| classification | string | greeting / business_card / other |
| description | string | 圖片描述 |
| structured_data | object|null | 名片解析結果 |
| reply_text | string|null | 回覆文字 |
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

OCR_PROMPT = """請從這張名片中提取以下資訊，嚴格以 JSON 格式回傳：
{
  "name": "姓名",
  "company": "公司名稱",
  "title": "職稱",
  "phone": "電話號碼",
  "email": "電子郵件",
  "address": "地址"
}
無法辨識的欄位設為 null。只回傳 JSON，不要其他文字。"""

CLASSIFY_PROMPT = "這張圖片是「問候」、「名片」還是「其他」？只回傳一個詞。"


async def execute(params: dict[str, Any]) -> dict[str, Any]:
    """Skill 統一進入點。"""
    image_b64 = params.get("image_base64", "")
    if not image_b64:
        return {"error": "image_base64 is required"}

    mode = params.get("mode", "auto")

    if mode == "auto":
        classification = await _classify(image_b64)
    else:
        classification = mode

    if classification == "greeting":
        return await _handle_greeting(image_b64, params.get("customer_name", ""))
    elif classification == "business_card":
        return await _handle_business_card(image_b64)
    elif classification == "other":
        return await _handle_other(image_b64)
    else:
        return {"classification": classification, "error": f"Unknown type: {classification}"}


async def _classify(image_b64: str) -> str:
    """分類圖片類型。"""
    from shared.multimedia import analyze_image

    content = base64.b64decode(image_b64)
    result = await analyze_image(content, prompt=CLASSIFY_PROMPT)
    result = result.strip().lower()

    if "問候" in result or "greeting" in result:
        return "greeting"
    elif "名片" in result or "business" in result or "card" in result:
        return "business_card"
    else:
        return "other"


async def _handle_greeting(image_b64: str, customer_name: str) -> dict[str, Any]:
    """問候圖片：生成個人化問候回覆。"""
    from shared.multimedia import analyze_image

    content = base64.b64decode(image_b64)
    desc = await analyze_image(content, prompt="請描述這張問候圖片的風格與氛圍")

    name = customer_name or "客戶"
    greeting = await analyze_image(
        content,
        prompt=f"根據以上描述，以{name}的名義，生成一個溫暖禮貌的問候回覆。風格與圖片氛圍一致。",
    )

    return {
        "classification": "greeting",
        "description": desc,
        "reply_text": greeting,
        "structured_data": None,
    }


async def _handle_business_card(image_b64: str) -> dict[str, Any]:
    """名片 OCR：提取結構化資訊。"""
    from shared.multimedia import analyze_image

    content = base64.b64decode(image_b64)
    result = await analyze_image(content, prompt=OCR_PROMPT)

    structured = None
    try:
        structured = json.loads(result)
    except json.JSONDecodeError:
        structured = {"raw": result}

    return {
        "classification": "business_card",
        "description": "名片資訊已提取",
        "structured_data": structured,
        "reply_text": None,
    }


async def _handle_other(image_b64: str) -> dict[str, Any]:
    """其他圖片：生成摘要。"""
    from shared.multimedia import analyze_image

    content = base64.b64decode(image_b64)
    desc = await analyze_image(content)

    return {
        "classification": "other",
        "description": desc,
        "structured_data": None,
        "reply_text": desc,
    }
