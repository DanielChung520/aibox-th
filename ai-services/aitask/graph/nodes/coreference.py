"""
Coreference resolver node.

# Last Update: 2026-04-11 08:54:32
# Author: AI Agent
# Version: 1.0.0
"""

import json
import re

import httpx
from langchain_core.messages import BaseMessage, HumanMessage

from aitask.config import AITaskSettings, settings
from aitask.graph.state import TopState

COREFERENCE_MARKERS = re.compile(r"(那個|這個|它|他們|她們|他|她|它們|呢|那些|這些|上面|前面|剛才)")
TOPIC_KEYWORDS = ("天氣", "庫存", "採購", "訂單", "銷售", "報表", "文件", "知識庫")


def _has_coreference(text: str) -> bool:
    return COREFERENCE_MARKERS.search(text) is not None


def _message_text(message: BaseMessage) -> str:
    content = message.content
    return content if isinstance(content, str) else str(content)


async def _resolve_with_llm(
    text: str,
    context_entities: dict[str, str],
    recent_messages: list[BaseMessage],
    settings_obj: AITaskSettings,
) -> str:
    recent_messages_text = "\n".join(
        f"{getattr(message, 'type', 'human')}: {_message_text(message)}"
        for message in recent_messages[-3:]
    )
    prompt = (
        "你是一個共指消解器。用戶的訊息中包含代詞或指示詞，請根據上下文將其替換為明確的指稱。\n\n"
        f"上下文實體：{json.dumps(context_entities, ensure_ascii=False)}\n"
        f"最近對話：\n{recent_messages_text or '無'}\n\n"
        f"用戶訊息：{text}\n\n"
        "請直接回覆改寫後的完整句子，不要加任何解釋。"
    )
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{settings_obj.provider.ollama_base_url.rstrip('/')}/api/generate",
                json={
                    "model": settings_obj.default_model,
                    "prompt": prompt,
                    "stream": False,
                },
            )
            response.raise_for_status()
            data = response.json()
        resolved = str(data.get("response", "")).strip()
        return resolved or text
    except (httpx.HTTPError, ValueError, TypeError, json.JSONDecodeError):
        return text
    except Exception:
        return text


def _extract_entities(text: str) -> dict[str, str]:
    for keyword in TOPIC_KEYWORDS:
        if keyword in text:
            return {"topic": keyword}
    return {}


async def resolve_coreference_node(state: TopState) -> dict[str, object]:
    messages = state["messages"]
    if not messages:
        return {"coreference_resolved": False}

    last_message = messages[-1]
    text = _message_text(last_message)
    context_entities = state.get("context_entities") or {}
    new_entities = _extract_entities(text)
    merged_entities = {**context_entities, **new_entities}

    if not _has_coreference(text):
        return {
            "coreference_resolved": False,
            "context_entities": merged_entities,
        }

    resolved_text = await _resolve_with_llm(text, context_entities, messages[-4:-1], settings)
    updated_message = HumanMessage(
        content=resolved_text,
        id=getattr(last_message, "id", None),
    )
    return {
        "coreference_resolved": True,
        "context_entities": merged_entities,
        "messages": [updated_message],
    }
