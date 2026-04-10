"""
Chat responder node.

# Last Update: 2026-04-11 02:57:52
# Author: AI Agent
# Version: 1.0.0
"""

from collections.abc import Sequence

import httpx
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from aitask.config import settings
from aitask.graph.state import TopState

DEFAULT_PROVIDER = "ollama"
TIMEOUT_SECONDS = 120.0


def _message_role(message: BaseMessage) -> str:
    if isinstance(message, HumanMessage):
        return "user"
    if isinstance(message, AIMessage):
        return "assistant"
    if isinstance(message, SystemMessage):
        return "system"
    return "user"


def _message_text(message: BaseMessage) -> str:
    content = message.content
    return content if isinstance(content, str) else str(content)


def _provider_config(provider: str) -> tuple[str, str, dict[str, str]]:
    provider_config = settings.provider
    if provider == "openai":
        return provider_config.openai_base_url.rstrip("/"), settings.default_model, {
            "Authorization": f"Bearer {provider_config.openai_api_key}"
        } if provider_config.openai_api_key else {}
    if provider == "minimax":
        return provider_config.minimax_base_url.rstrip("/"), settings.default_model, {
            "Authorization": f"Bearer {provider_config.minimax_api_key}"
        } if provider_config.minimax_api_key else {}
    if provider == "gemini":
        return provider_config.gemini_base_url.rstrip("/"), settings.default_model, {
            "x-goog-api-key": provider_config.gemini_api_key
        } if provider_config.gemini_api_key else {}
    if provider == "anthropic":
        headers = {"anthropic-version": "2023-06-01", "content-type": "application/json"}
        if provider_config.anthropic_api_key:
            headers["x-api-key"] = provider_config.anthropic_api_key
        return provider_config.anthropic_base_url.rstrip("/"), settings.default_model, headers
    return provider_config.ollama_base_url.rstrip("/"), settings.default_model, {}


def _state_messages(messages: Sequence[BaseMessage]) -> list[dict[str, str]]:
    return [{"role": _message_role(message), "content": _message_text(message)} for message in messages]


async def _request_response(messages: list[dict[str, str]]) -> str:
    provider = DEFAULT_PROVIDER
    base_url, model, headers = _provider_config(provider)
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        if provider == "gemini":
            response = await client.post(
                f"{base_url}/models/{model}:generateContent",
                json={
                    "contents": [
                        {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
                        for m in messages
                    ]
                },
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            return "".join(
                part.get("text", "")
                for candidate in data.get("candidates", [])
                for part in candidate.get("content", {}).get("parts", [])
            )
        if provider == "anthropic":
            system_messages = [m["content"] for m in messages if m["role"] == "system"]
            response = await client.post(
                f"{base_url}/v1/messages",
                json={
                    "model": model,
                    "messages": [m for m in messages if m["role"] != "system"],
                    "temperature": 0.7,
                    "system": "\n".join(system_messages) if system_messages else None,
                },
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            return "".join(block.get("text", "") for block in data.get("content", []))
        endpoint = "/api/chat" if provider == "ollama" else "/chat/completions"
        payload: dict[str, object] = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
        }
        if provider == "ollama":
            payload["stream"] = False
        response = await client.post(f"{base_url}{endpoint}", json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        if provider == "ollama":
            message = data.get("message", {})
            return str(message.get("content", ""))
        choices = data.get("choices", [])
        if not choices:
            return ""
        return str(choices[0].get("message", {}).get("content", ""))


async def chat_responder_node(state: TopState) -> dict[str, object]:
    response_text = await _request_response(_state_messages(state["messages"]))
    return {
        "messages": [AIMessage(content=response_text)],
        "state_version": state["state_version"] + 1,
    }
