"""
@file        Ragic Agent — Ragic 處理節點 v1.1
@lastUpdate  2026-04-27 22:30:00
@author      AI Agent
@version     1.1.0
"""

import logging, httpx
from typing import Any
from langchain_core.messages import AIMessage
from bpa.ragic_agent.config import KNOWLEDGE_AGENT_URL, OLLAMA_BASE_URL, RAGIC_KB_ROOT_ID, RAGIC_MODEL, SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def _search_hybrid_rag(query: str) -> list[dict[str, str]]:
    try:
        resp = httpx.post(
            f"{KNOWLEDGE_AGENT_URL.rstrip('/')}/hybrid/search",
            json={"query": query, "top_k": 3, "root_id": RAGIC_KB_ROOT_ID},
            timeout=15.0,
        )
        if resp.status_code == 200:
            return resp.json().get("results", [])
    except Exception as e:
        logger.warning(f"KA HybridRAG failed: {e}")
    return []


def _call_ollama(messages: list[dict[str, str]], model: str | None = None) -> str:
    try:
        resp = httpx.post(
            f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat",
            json={"model": model or RAGIC_MODEL, "messages": messages, "stream": False},
            timeout=120.0,
        )
        if resp.status_code == 200:
            return str(resp.json().get("message", {}).get("content", ""))
    except Exception as e:
        logger.error(f"Ollama failed: {e}")
    return "抱歉，我暫時無法處理您的請求。"


COMPLAINT_SYSTEM = "使用者表達了不滿。請用溫暖、專業的語氣回應，表達理解並承諾會記錄與改善。簡短回應即可。"


async def ragic_handler_node(state: dict[str, Any]) -> dict[str, Any]:
    messages = state.get("messages", [])
    intent = state.get("current_intent", "general_chat")
    user_text = str(messages[-1].content) if messages and hasattr(messages[-1], "content") else ""

    history: list[dict[str, str]] = []
    for msg in messages[-20:]:
        role = "user" if getattr(msg, "type", "") == "human" else "assistant"
        content = str(msg.content) if hasattr(msg, "content") else str(msg)
        history.append({"role": role, "content": content})

    if intent == "complaint":
        reply = _call_ollama([{"role": "system", "content": COMPLAINT_SYSTEM}, {"role": "user", "content": user_text}])
    elif intent == "ragic_question":
        knowledge_results = _search_hybrid_rag(user_text)
        msg_list = [{"role": "system", "content": SYSTEM_PROMPT}]
        if knowledge_results:
            kb = "以下是 Ragic 知識庫資訊（KA HybridRAG 檢索）：\n\n"
            for i, r in enumerate(knowledge_results[:3], 1):
                kb += f"[{i}]《{r.get('source','?')}》：{r.get('content','')[:500]}\n\n"
            msg_list.append({"role": "system", "content": kb})
        msg_list.extend(history)
        reply = _call_ollama(msg_list)
    else:
        reply = _call_ollama([{"role": "system", "content": SYSTEM_PROMPT}, *history])

    logger.info(f"[RagicHandler] intent={intent} reply_len={len(reply)}")
    return {"messages": [AIMessage(content=reply)], "state_version": state.get("state_version", 0) + 1}
