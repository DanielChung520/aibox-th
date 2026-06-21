"""
@file        customer_safe_reply/skill.py
@description 客戶安全回覆 Skill：針對不明意圖的客戶訊息，以 LLM 生成安全回應
@lastUpdate  2026-06-20
@author      Sisyphus
@version     1.0.0

# Skill 規範
## 用途
針對無法明確分類的客戶訊息，以受限的 LLM 生成安全回覆，
system prompt 嵌入 L0-L4 權限規則，防止 jailbreak。
"""

from __future__ import annotations
import logging
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = """你是一個專業親切的客服助手，服務於台灣福祉股份有限公司。

【資訊安全規則 — 嚴格遵守】
- L0（公開資訊）：產品介紹、服務項目、營業時間 → 可直接回覆
- L1（FAQ）：常見問題、使用說明 → 可回覆
- L2（互動摘要）：Timeline 時間/類型/摘要 → 僅摘要，不含明細
- L3（機密明細）：報價金額、訂單成本、合約條款 → 婉轉拒答
- L4（內部操作）：下單、改單、取消訂單 → 婉轉拒答

【禁止行為】
- 嚴禁自行編造產品資訊、價格、庫存資料
- 嚴禁透露任何客戶的個人資料
- 不可執行任何訂單操作"""


async def execute(params: dict[str, Any]) -> dict[str, Any]:
    from shared.llm_resolver import resolve_and_call

    message = params.get("message", "")
    system_prompt = params.get("system_prompt", DEFAULT_SYSTEM_PROMPT)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": message},
    ]

    result = await resolve_and_call(
        messages=messages,
        model="ollama:gemma4:31b",
        temperature=0.3,
        max_tokens=256,
    )

    return {
        "reply_text": result.get("content", ""),
        "blocked": False,
    }
