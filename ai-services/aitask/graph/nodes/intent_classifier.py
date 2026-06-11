"""
3-layer intent classifier node.

# Last Update: 2026-04-11 08:54:32
# Author: AI Agent
# Version: 1.0.0
"""

import json
import re

import httpx

from aitask.config import AITaskSettings, settings
from aitask.graph.state import TopState
from aitask.top_intent_rag.config import get_matching_threshold

VALID_INTENTS = {"general_chat", "data_query", "knowledge", "tool_use", "bpa_task"}
RULE_PATTERNS: dict[str, re.Pattern[str]] = {
    "data_query": re.compile(
        r"(查詢|查看|報表|統計|列出|顯示|多少|數據|訂單|採購|庫存|銷售)",
        re.IGNORECASE,
    ),
    "knowledge": re.compile(
        r"(知識|文件|文檔|搜尋知識|查找資料|根據文件|參考資料)",
        re.IGNORECASE,
    ),
    "tool_use": re.compile(
        r"(執行|運行|啟動|工具|MCP|plugin|外掛)",
        re.IGNORECASE,
    ),
    "bpa_task": re.compile(
        r"(流程|審批|簽核|BPA|物料|請購|採購單|工作流)",
        re.IGNORECASE,
    ),
}
CLASSIFY_PROMPT = """你是一個意圖分類器。根據用戶的訊息，判斷其意圖類別。

可選意圖：
- general_chat: 一般對話、問候、閒聊
- data_query: 數據查詢、報表、統計相關
- knowledge: 知識庫搜尋、文件查找
- tool_use: 使用工具、執行外部操作
- bpa_task: 業務流程、審批、簽核

用戶訊息：{message}

請只回覆一個 JSON 物件，格式如下：
{{"intent": "意圖名稱", "confidence": 0.0到1.0的浮點數}}
"""


def _map_intent(raw_intent: str) -> str:
    normalized_intent = raw_intent.strip().lower()
    if normalized_intent in VALID_INTENTS:
        return normalized_intent
    aliases: dict[str, str] = {
        "query": "data_query",
        "search": "knowledge",
        "tool": "tool_use",
        "bpa": "bpa_task",
        "chat": "general_chat",
    }
    return aliases.get(normalized_intent, "general_chat")


def _message_text(state: TopState) -> str:
    last_message = state["messages"][-1]
    return (
        last_message.content
        if isinstance(last_message.content, str)
        else str(last_message.content)
    )


def _try_rule_match(text: str) -> tuple[str, float] | None:
    cleaned_text = text.strip()
    if not cleaned_text:
        return None
    for intent, pattern in RULE_PATTERNS.items():
        if pattern.search(cleaned_text):
            return (intent, 0.95)
    return None


async def _get_embedding(
    text: str, ollama_base_url: str, embedding_model: str
) -> list[float]:
    """Get embedding vector from Ollama."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{ollama_base_url.rstrip('/')}/api/embed",
            json={"model": embedding_model, "input": text},
        )
        response.raise_for_status()
        data = response.json()
    embeddings = data.get("embeddings", [])
    if isinstance(embeddings, list) and embeddings:
        first_embedding = embeddings[0]
        if isinstance(first_embedding, list):
            return [float(value) for value in first_embedding]
    return []


async def _try_semantic_match(
    text: str, settings_obj: AITaskSettings
) -> tuple[str, float] | None:
    """Try Qdrant semantic intent matching."""
    ollama_url = settings_obj.provider.ollama_base_url
    qdrant_url = settings_obj.services.qdrant_url
    embedding_model = "bge-m3"
    collection = "orchestrator_intents"
    threshold = await get_matching_threshold()
    try:
        embedding = await _get_embedding(text, ollama_url, embedding_model)
        if not embedding:
            return None
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{qdrant_url.rstrip('/')}/collections/{collection}/points/search",
                json={"vector": embedding, "limit": 3, "with_payload": True},
            )
            response.raise_for_status()
            data = response.json()
        results = data.get("result", [])
        if not isinstance(results, list):
            return None
        for result in results:
            if not isinstance(result, dict):
                continue
            score = float(result.get("score", 0.0))
            if score < threshold:
                continue
            payload = result.get("payload", {})
            if not isinstance(payload, dict):
                continue
            intent_id = str(payload.get("intent_id", "general_chat"))
            return (_map_intent(intent_id), score)
        return None
    except (httpx.HTTPError, ValueError, TypeError, json.JSONDecodeError):
        return None
    except Exception:
        return None


async def _try_llm_classify(
    text: str, settings_obj: AITaskSettings
) -> tuple[str, float]:
    """LLM-based intent classification as final fallback."""
    ollama_url = settings_obj.provider.ollama_base_url
    model = settings_obj.default_model
    prompt = CLASSIFY_PROMPT.format(message=text)
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{ollama_url.rstrip('/')}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                },
            )
            response.raise_for_status()
            data = response.json()
        response_text = str(data.get("response", "{}"))
        parsed = json.loads(response_text)
        if not isinstance(parsed, dict):
            return ("general_chat", 0.3)
        intent = str(parsed.get("intent", "general_chat"))
        confidence = float(parsed.get("confidence", 0.5))
        bounded_confidence = max(0.0, min(confidence, 0.85))
        return (_map_intent(intent), bounded_confidence)
    except (httpx.HTTPError, ValueError, TypeError, json.JSONDecodeError):
        return ("general_chat", 0.3)
    except Exception:
        return ("general_chat", 0.3)


async def classify_intent_node(state: TopState) -> dict[str, object]:
    """Classify user intent using 3-layer cascade: rule → semantic → LLM."""
    messages = state["messages"]
    if not messages:
        return {
            "current_intent": "general_chat",
            "intent_confidence": 0.0,
            "intent_method": "rule",
        }

    text = _message_text(state)
    rule_result = _try_rule_match(text)
    if rule_result is not None:
        return {
            "current_intent": rule_result[0],
            "intent_confidence": rule_result[1],
            "intent_method": "rule",
        }

    semantic_result = await _try_semantic_match(text, settings)
    if semantic_result is not None:
        return {
            "current_intent": semantic_result[0],
            "intent_confidence": semantic_result[1],
            "intent_method": "semantic",
        }

    llm_result = await _try_llm_classify(text, settings)
    return {
        "current_intent": llm_result[0],
        "intent_confidence": llm_result[1],
        "intent_method": "llm",
    }
