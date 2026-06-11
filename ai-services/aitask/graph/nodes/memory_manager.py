"""
Memory manager node.

# Last Update: 2026-04-11 08:54:32
# Author: AI Agent
# Version: 1.0.0
"""

import httpx
from langchain_core.messages import BaseMessage

from aitask.config import AITaskSettings, settings
from aitask.graph.state import TopState

SLIDING_WINDOW_SIZE = 10
SUMMARIZATION_THRESHOLD = 20


def _message_text(message: BaseMessage) -> str:
    content = message.content
    return content if isinstance(content, str) else str(content)


def _message_role(message: BaseMessage) -> str:
    message_type = getattr(message, "type", "human")
    if message_type == "human":
        return "user"
    if message_type == "ai":
        return "assistant"
    return "system"


def _memory_entry(message: BaseMessage) -> dict[str, object]:
    return {"role": _message_role(message), "content": _message_text(message)}


async def _summarize_messages(
    messages: list[BaseMessage], settings_obj: AITaskSettings
) -> str:
    conversation_text = "\n".join(
        f"{_message_role(message)}: {_message_text(message)}" for message in messages
    )
    prompt = (
        "請將以下對話內容摘要成一段簡潔的描述，保留關鍵資訊：\n\n"
        f"{conversation_text}\n\n"
        "摘要："
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
        summary = str(data.get("response", "")).strip()
        return summary or "對話摘要不可用"
    except (httpx.HTTPError, ValueError, TypeError):
        return "對話摘要不可用"
    except Exception:
        return "對話摘要不可用"


async def memory_manager_node(state: TopState) -> dict[str, object]:
    messages = state["messages"]
    turn_count = state["memory_turn_count"] + 1
    long_term_memory = list(state.get("long_term_memory") or [])

    if len(messages) > SLIDING_WINDOW_SIZE:
        trimmed = messages[-SLIDING_WINDOW_SIZE:]
        overflow = messages[:-SLIDING_WINDOW_SIZE]
    else:
        trimmed = messages
        overflow = []

    short_term_memory = [_memory_entry(message) for message in trimmed]

    if turn_count >= SUMMARIZATION_THRESHOLD and overflow:
        summary = await _summarize_messages(overflow, settings)
        long_term_memory.append(
            {"type": "summary", "content": summary, "turn_count": turn_count}
        )

    return {
        "messages": trimmed,
        "short_term_memory": short_term_memory,
        "long_term_memory": long_term_memory,
        "memory_turn_count": turn_count,
        "checkpoint_version": state["checkpoint_version"] + 1,
    }
