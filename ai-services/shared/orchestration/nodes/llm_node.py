"""
@file        LLM node
@description Standard LLM call node with function calling support.
@lastUpdate  2026-04-21 10:00:00
@author      Daniel Chung
@version     1.0.0
"""

import os
from typing import Any

import httpx
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")


def _message_to_dict(message: BaseMessage) -> dict[str, str]:
    role = "user"
    if isinstance(message, AIMessage):
        role = "assistant"
    elif isinstance(message, HumanMessage):
        role = "user"
    content = message.content
    return {"role": role, "content": content if isinstance(content, str) else str(content)}


def _extract_tool_calls(response_data: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(response_data, dict):
        return []

    if response_data.get("tool_calls"):
        return response_data["tool_calls"]

    message = response_data.get("message", {})
    if isinstance(message, dict) and message.get("tool_calls"):
        return message["tool_calls"]

    return []


async def llm_node(
    state: dict[str, Any],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    messages = state.get("messages", [])
    messages_dict = [_message_to_dict(m) for m in messages if isinstance(m, (HumanMessage, AIMessage))]

    payload: dict[str, Any] = {
        "model": model or DEFAULT_MODEL,
        "messages": messages_dict,
        "stream": False,
        "temperature": temperature,
        "options": {"num_predict": max_tokens},
    }
    if tools:
        payload["tools"] = tools

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload)
        resp.raise_for_status()
        response_data: dict[str, Any] = resp.json()

    assistant_message = response_data.get("message", {})
    content = assistant_message.get("content", "") if isinstance(assistant_message, dict) else ""

    tool_calls = _extract_tool_calls(response_data)

    result: dict[str, Any] = {
        "messages": [AIMessage(content=content)],
        "state_version": state.get("state_version", 0) + 1,
    }

    if tool_calls:
        result["pending_tool_calls"] = tool_calls

    return result