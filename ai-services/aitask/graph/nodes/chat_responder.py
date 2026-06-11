"""
Chat responder node.

# Last Update: 2026-04-27 13:00:00
# Author: AI Agent
# Version: 1.2.0
"""

import logging
import os
from collections.abc import Sequence

import httpx
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from aitask.config import settings
from aitask.graph.state import TopState

DEFAULT_PROVIDER = "ollama"
TIMEOUT_SECONDS = 120.0
EMOTION_MODEL = os.environ.get("AITASK_EMOTION_MODEL", "qwen3.5:0.8b")

EMOTION_INTENTS = {"orch_greeting", "orch_thanks", "orch_apology", "orch_blessing"}

EMOTION_PROMPT = """你是一個友善的客服助理。根據用戶的情緒給予溫暖、自然的回應。

用戶輸入：{user_input}

請直接回應一句話就好，簡短、友善、溫暖。不要加任何解釋或說明。"""


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


async def _request_response_streaming(messages: list[dict[str, str]]) -> str:
    """Call Ollama via ChatOllama with streaming, so astream_events emits on_chat_model_stream."""
    provider = DEFAULT_PROVIDER
    base_url, model, _headers = _provider_config(provider)
    llm = ChatOllama(
        model=model,
        base_url=base_url,
        temperature=0.7,
        streaming=True,
        timeout=TIMEOUT_SECONDS,
    )
    lc_messages: list[BaseMessage] = []
    for m in messages:
        role = m["role"]
        content = m["content"]
        if role == "system":
            lc_messages.append(SystemMessage(content=content))
        elif role == "assistant":
            lc_messages.append(AIMessage(content=content))
        else:
            lc_messages.append(HumanMessage(content=content))

    response = await llm.ainvoke(lc_messages)
    content = response.content
    return content if isinstance(content, str) else str(content)


async def _request_response(messages: list[dict[str, str]]) -> str:
    """Fallback: raw httpx call for non-Ollama providers."""
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


def _is_emotion_intent(matched_data: dict | None) -> bool:
    """Check if matched intent is an emotion response intent."""
    if not matched_data:
        return False
    best = matched_data.get("best_match") or matched_data
    intent_id = best.get("intent_id", "")
    return intent_id in EMOTION_INTENTS


async def _generate_emotion_response(user_input: str) -> str:
    """Generate emotion response using tiny LLM."""
    prompt = EMOTION_PROMPT.format(user_input=user_input)
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{settings.provider.ollama_base_url.rstrip('/')}/api/generate",
            json={
                "model": EMOTION_MODEL,
                "prompt": prompt,
                "stream": False,
                "temperature": 0.8,
            },
        )
        response.raise_for_status()
        data = response.json()
        return str(data.get("response", "")).strip()


async def chat_responder_node(state: TopState) -> dict[str, object]:
    messages = state["messages"]
    matched_data = state.get("matched_intent_data")

    if _is_emotion_intent(matched_data) and messages:
        last_message = messages[-1]
        user_input = last_message.content if isinstance(last_message.content, str) else str(last_message.content)
        try:
            response_text = await _generate_emotion_response(user_input)
        except Exception:
            logging.getLogger(__name__).warning("Emotion LLM failed, falling back to chat_responder", exc_info=True)
            response_text = await _request_response_streaming(_state_messages(messages))
    else:
        response_text = await _request_response_streaming(_state_messages(messages))

    return {
        "messages": [AIMessage(content=response_text)],
        "state_version": state["state_version"] + 1,
    }
