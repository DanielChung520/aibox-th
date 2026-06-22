"""
@file        image_processor/skill.py
@description 圖片分類與處理 Skill：名片OCR、賀卡回賀、業務圖片、一般圖片
@lastUpdate  2026-06-22
@author      Daniel Chung
@version     2.0.0

# Skill 規範

## 用途
接收圖片（base64），自動分類並執行對應處理：
- business_card → OCR 提取姓名/職稱 → 生成感謝回覆 → 回傳結構化資料供建檔
- greeting → 偵測圖片語言 → 感謝{稱謂} + 文學回賀/回問安（50字內）
- business_image → 表格/訂單/業務相關圖片 → 「收到，會盡快聯繫業務」
- other → 一般圖片 → 「感謝您的分享 😊」

## 輸入
| 參數 | 類型 | 必填 | 說明 |
|------|------|------|------|
| image_base64 | string | ✅ | base64 編碼圖片 |
| mode | enum | ❌ | auto / business_card / greeting / business_image / other |
| contact_name | string | ❌ | 聯絡人稱謂（如「鍾副總」、「藍老師」）|
| sales_contact | string | ❌ | 業務本人稱謂/姓名（給 business_image 用）|

## 輸出
| 屬性 | 類型 | 說明 |
|------|------|------|
| classification | string | business_card / greeting / business_image / other |
| description | string | 圖片描述 |
| language | string | 偵測到的語言代碼（zh-CN / zh-TW / en / ja / etc）|
| structured_data | object|null | 名片解析結果 {name, title, company, phone, email, address} |
| reply_text | string | 回覆文字 |
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

MLX_API = os.getenv("MLX_BASE_URL", "http://127.0.0.1:11400/v1")
VISION_MODEL = os.getenv("VISION_MODEL", "Qwen3-VL-8B")

# ---------------------------------------------------------------------------
# 通用 LLM 呼叫（MLX OpenAI-compatible API）
# ---------------------------------------------------------------------------

async def _call_mlx(messages: list, max_tokens: int = 500, temperature: float = 0.3) -> str:
    """呼叫 MLX API 的 chat/completions 端點。"""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{MLX_API}/chat/completions", json={
                "model": VISION_MODEL,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            })
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.warning(f"[image_processor] MLX call failed: {e}")
    return ""


async def _vision(prompt: str, image_b64: str) -> str:
    """Vision 分析：傳圖片給多模態模型。"""
    return await _call_mlx([
        {"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
        ]}
    ], max_tokens=600, temperature=0.3)


async def _llm(system: str, user: str, max_tok: int = 300, temp: float = 0.7) -> str:
    """純文字 LLM 呼叫（無圖片）。"""
    return await _call_mlx([
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ], max_tokens=max_tok, temperature=temp)


# ---------------------------------------------------------------------------
# TITLES 尊稱對應表（同 webhook.py）
# ---------------------------------------------------------------------------

TITLES = {
    "副總經理":"總經理", "總經理":"總經理", "協理":"協理", "經理":"經理", "副理":"經理",
    "主任":"主任", "組長":"組長", "工程師":"老師", "設計師":"老師", "分析師":"老師",
    "導入師":"老師", "醫師":"老師", "律師":"老師", "教授":"老師", "副總":"副總",
    "董事長":"執行長", "執行長":"執行長", "院長":"院長", "所長":"所長", "顧問":"顧問", "專員":"專員",
}


def _resolve_greeting(name: str, title: str) -> str:
    """從姓名+職稱解析稱謂（同 webhook.py 邏輯）。"""
    surname = next((ch for ch in name if '\u4e00' <= ch <= '\u9fff'), "")
    raw_title = title if title and not any(title.endswith(k) for k in ["公司","企業","集團","行號"]) else ""
    matched = next((short for t, short in TITLES.items() if t in raw_title), "")
    if surname and matched:
        return f"{surname}老師" if matched == "老師" else f"{surname}{matched}"
    elif surname:
        return f"{surname}老師"
    return "您"


async def _detect_language(desc: str) -> str:
    """從圖片描述偵測主要語言。"""
    lang = await _llm(
        "你是一個語言偵測助手。根據文字內容，判斷主要使用哪種語言。只回傳語言代碼。",
        f"文字內容：{desc}\n\n語言代碼範例：zh-TW（台灣繁體）、zh-CN（簡體）、en（英文）、ja（日文）。只回傳代碼。",
        max_tok=10, temp=0.1
    )
    lang = lang.strip().upper()
    if lang not in ("ZH-TW", "ZH-CN", "EN", "JA", "KO", "VI", "TH", "ID"):
        return "ZH-TW"  # 預設繁體中文
    return lang


# ---------------------------------------------------------------------------
# 分類
# ---------------------------------------------------------------------------

async def _classify(image_b64: str) -> str:
    """先用 vision 分析內容，再分類。支援 business_card / greeting / business_image / other。"""
    desc = await _vision("請用繁體中文詳細描述這張圖片的內容，包含所有文字。", image_b64)
    if not desc:
        return "other", ""

    # 名片特徵
    card_kws = ["名片", "公司", "電話", "姓名", "手機", "email", "統編", "職稱", "地址"]
    # 賀卡/問候特徵
    greet_kws = ["早安", "午安", "晚安", "祝福", "生日", "新年", "端午", "中秋", "聖誕",
                 "母親節", "父親節", "情人節", "元宵", "賀卡", "恭喜", "賀年",
                 "春聯", "紅包", "燈籠", "龍舟", "粽子", "月餅"]
    # 業務圖片特徵
    biz_kws = ["訂單", "報價", "銷貨", "發票", "合約", "單據", "表格", "Excel", "明細",
               "採購", "出貨", "申請單", "請款", "收據", "憑證", "文件"]

    desc_lower = desc.lower()

    if any(k in desc for k in card_kws):
        return "business_card", desc
    elif any(k in desc_lower for k in greet_kws):
        return "greeting", desc
    elif any(k in desc for k in biz_kws):
        return "business_image", desc
    else:
        return "other", desc


# ---------------------------------------------------------------------------
# 四大處理分支
# ---------------------------------------------------------------------------

async def _handle_business_card(image_b64: str, desc: str) -> dict:
    """a. 名片：提取姓名/職稱/公司 → 生成感謝回覆。"""
    # 提取結構化資料
    raw = await _llm(
        "你是一個名片OCR助手。從以下名片描述提取 JSON，包含 name/title/company/phone/email/address。無法辨識的欄位設為 null。只回 JSON。",
        f"名片描述：{desc[:800]}",
        max_tok=300, temp=0.1
    )
    structured = None
    try:
        structured = json.loads(raw)
    except json.JSONDecodeError:
        structured = {"raw": raw}

    name = (structured or {}).get("name", "") or ""
    title = (structured or {}).get("title", "") or ""
    company = (structured or {}).get("company", "") or ""

    # 解析稱謂
    greeting = _resolve_greeting(name, title)

    # 偵測語言
    check_text = f"{name} {company}"
    is_chinese = any('\u4e00' <= c <= '\u9fff' for c in check_text)

    if is_chinese:
        reply = await _llm(
            "你是台灣的業務助理，只能用繁體中文，不可以夾雜英文。",
            f"用繁體中文寫這句話：{greeting}，感謝您分享名片，很高興認識您。全中文，不要任何英文單字。",
            max_tok=100, temp=0.7
        )
    else:
        reply = await _llm(
            "You are a professional business assistant. Respond politely and warmly.",
            f'Address the person as "{greeting}", thank them for sharing their business card, express pleasure in meeting them. One sentence only.',
            max_tok=100, temp=0.7
        )

    return {
        "classification": "business_card",
        "description": desc[:200],
        "language": "zh-TW" if is_chinese else "en",
        "structured_data": structured,
        "reply_text": reply or f"{greeting}，感謝您分享名片，很高興認識您。",
    }


async def _handle_greeting(image_b64: str, desc: str, contact_name: str = "") -> dict:
    """b. 賀卡/問安：感謝{稱謂} + 文學回賀（50字內）。"""
    # 偵測語言
    lang = await _detect_language(desc)

    addr = contact_name or "您"

    if lang == "ZH-TW":
        reply = await _llm(
            "你是溫暖真誠的業務助理，用繁體中文，簡潔有力。",
            f"{addr}傳了一張節慶/問候圖片。\n圖片描述：{desc}\n\n請先感謝{addr}的祝福，再接一句簡短優美應景的話（30~50字）。全文不超過60字。不要詩詞堆砌，不要分段。",
            max_tok=200, temp=0.7
        )
    elif lang == "ZH-CN":
        reply = await _llm(
            "你是温暖的业务助理，用简体中文，简洁有力。",
            f"{addr}发了一张节日/问候图片。\n图片描述：{desc}\n\n请先感谢{addr}的祝福，再接一句简短优美应景的话（30~50字）。全文不超过60字。",
            max_tok=200, temp=0.7
        )
    else:  # EN / 其他
        reply = await _llm(
            "You are a warm and sincere assistant. Be concise.",
            f"{addr} sent a holiday/greeting image.\nDescription: {desc}\n\nThank {addr} for the greeting, then add one short poetic sentence (30-50 words) fitting the occasion.",
            max_tok=200, temp=0.7
        )

    return {
        "classification": "greeting",
        "description": desc[:200],
        "language": lang,
        "structured_data": None,
        "reply_text": reply or f"感謝{addr}的祝福！",
    }


async def _handle_business_image(desc: str, sales_contact: str = "") -> dict:
    """c. 業務圖片：表格/訂單 → 通知將聯繫業務。"""
    sales = sales_contact or "業務專員"
    reply = f"收到，我會盡快聯繫{sales}處理。"
    return {
        "classification": "business_image",
        "description": desc[:200],
        "language": "zh-TW",
        "structured_data": None,
        "reply_text": reply,
    }


async def _handle_other(desc: str) -> dict:
    """d. 一般圖片 → 簡單感謝。"""
    return {
        "classification": "other",
        "description": desc[:200],
        "language": "zh-TW",
        "structured_data": None,
        "reply_text": "感謝您的分享 😊",
    }


# ---------------------------------------------------------------------------
# 統一進入點
# ---------------------------------------------------------------------------

async def execute(params: dict[str, Any]) -> dict[str, Any]:
    """Skill 統一進入點。

    Args:
        params: 見上方 Skill 規範 §輸入

    Returns:
        見上方 Skill 規範 §輸出
    """
    image_b64 = params.get("image_base64", "")
    if not image_b64:
        return {"error": "image_base64 is required"}

    mode = params.get("mode", "auto")

    if mode == "auto":
        classification, desc = await _classify(image_b64)
    else:
        classification = mode
        desc = await _vision("請用繁體中文詳細描述這張圖片的內容，包含所有文字。", image_b64)

    if classification == "business_card":
        return await _handle_business_card(image_b64, desc)
    elif classification == "greeting":
        return await _handle_greeting(image_b64, desc, params.get("contact_name", ""))
    elif classification == "business_image":
        return await _handle_business_image(desc, params.get("sales_contact", ""))
    elif classification == "other":
        return await _handle_other(desc)
    else:
        return {"classification": classification, "error": f"Unknown type: {classification}"}
