"""
@file        Ragic Agent — 意圖分類節點
@lastUpdate  2026-04-27 22:30:00
@author      AI Agent
@version     1.1.0
"""

import json, logging, re, httpx
from typing import Any
from bpa.ragic_agent.config import OLLAMA_BASE_URL

logger = logging.getLogger(__name__)

RULE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("complaint", re.compile(r"(抱怨|客訴|不滿|問題回報|投訴|不好用|爛|生氣|bug|錯誤|難用)", re.IGNORECASE)),
    ("ragic_question", re.compile(r"(Ragic|表單|欄位|新增|修改|刪除|查詢|匯出|報表|權限|篩選|排序|上傳|下載)", re.IGNORECASE)),
]

INTENT_PROMPT = """分析使用者訊息。只回覆 JSON：{message}
{{
  "intent": "ragic_question | complaint | general_chat",
  "confidence": 0.0~1.0,
  "keywords": ["關鍵詞"]
}}"""


async def classify_intent(state: dict[str, Any]) -> dict[str, Any]:
    messages = state.get("messages", [])
    if not messages:
        return {"action_plan": "direct_answer", "current_intent": "general_chat", "intent_confidence": 0.5}

    text = str(messages[-1].content) if hasattr(messages[-1], "content") else str(messages[-1])

    for intent, pattern in RULE_PATTERNS:
        if pattern.search(text):
            logger.info(f"[RagicIntent] rule match: {intent}")
            return {"action_plan": "direct_answer", "current_intent": intent, "intent_confidence": 0.9, "intent_method": "rule", "complaint_detected": intent == "complaint"}

    # LLM fallback with sync httpx (runs inside run_until_complete)
    try:
        resp = httpx.post(
            f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat",
            json={"model": "qwen3.5:0.8b", "messages": [{"role": "user", "content": INTENT_PROMPT.format(message=text)}], "stream": False, "format": "json"},
            timeout=15.0,
        )
        if resp.status_code == 200:
            content = resp.json().get("message", {}).get("content", "{}")
            result = json.loads(content)
            return {"action_plan": "direct_answer", "current_intent": result.get("intent", "general_chat"), "intent_confidence": result.get("confidence", 0.5), "intent_method": "llm"}
    except Exception as e:
        logger.warning(f"Intent LLM failed: {e}")

    return {"action_plan": "direct_answer", "current_intent": "general_chat", "intent_confidence": 0.5}
