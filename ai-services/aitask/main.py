"""
AITask Service - AI Chat Service

Provides natural language conversation with streaming support,
and 5W1H tagging for chat sessions.

# Last Update: 2026-04-10 21:30:00
# Author: Daniel Chung
# Version: 1.2.0
"""

import json
import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import httpx
from arango import ArangoClient  # type: ignore[attr-defined]
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from aitask.collections import ensure_collections
from aitask.config import settings

logger = logging.getLogger("aitask")


@asynccontextmanager
async def lifespan(app_instance: FastAPI) -> AsyncGenerator[None, None]:
    client = ArangoClient(hosts=settings.arango.url)
    db = client.db(
        settings.arango.db_name,
        username=settings.arango.username,
        password=settings.arango.password,
    )
    await ensure_collections(db)
    logger.info("ArangoDB collections ensured")
    yield


app = FastAPI(
    title="AIBox AITask Service",
    description="AI Chat service with multi-provider streaming support.",
    version="1.3.0",
    lifespan=lifespan,
)

OLLAMA_BASE_URL = settings.provider.ollama_base_url
OPENAI_BASE_URL = settings.provider.openai_base_url
ANTHROPIC_BASE_URL = settings.provider.anthropic_base_url
GEMINI_BASE_URL = settings.provider.gemini_base_url
MINIMAX_BASE_URL = settings.provider.minimax_base_url

OPENAI_API_KEY = settings.provider.openai_api_key
MINIMAX_API_KEY = settings.provider.minimax_api_key
ANTHROPIC_API_KEY = settings.provider.anthropic_api_key
GEMINI_API_KEY = settings.provider.gemini_api_key

DEFAULT_MODEL = settings.default_model


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    model: Optional[str] = None
    stream: bool = True
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    provider: Optional[str] = "ollama"
    provider_base_url: Optional[str] = None  # Override default base URL
    api_key: Optional[str] = None  # API key from model_providers


class ChatResponse(BaseModel):
    model: str
    message: ChatMessage
    done: bool


class ServiceInfo(BaseModel):
    service: str
    description: str
    version: str
    port: int
    status: str


class HealthResponse(BaseModel):
    status: str
    service: str


class TaggingMessage(BaseModel):
    role: str
    content: str


class Tag5W1HRequest(BaseModel):
    session_key: str
    messages: list[TaggingMessage]
    model: Optional[str] = None


class Tag5W1HResponse(BaseModel):
    session_key: str
    tags: dict[str, str]


@app.get("/", response_model=ServiceInfo)
def root() -> ServiceInfo:
    return ServiceInfo(
        service="aitask",
        description="AI Chat service with multi-provider streaming",
        version="1.2.0",
        port=8001,
        status="running",
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="aitask")


def get_provider_config(provider: str, provider_base_url: Optional[str]) -> tuple[str, str]:
    """Get the API base URL and model prefix for a provider."""
    if provider_base_url:
        # Use the provided base URL
        base_url = provider_base_url.rstrip("/")
    elif provider == "ollama":
        base_url = OLLAMA_BASE_URL.rstrip("/")
    elif provider == "openai":
        base_url = OPENAI_BASE_URL.rstrip("/")
    elif provider == "anthropic":
        base_url = ANTHROPIC_BASE_URL.rstrip("/")
    elif provider == "gemini":
        base_url = GEMINI_BASE_URL.rstrip("/")
    elif provider == "minimax":
        base_url = MINIMAX_BASE_URL.rstrip("/")
    else:
        base_url = OLLAMA_BASE_URL.rstrip("/")

    # Model prefix for API path
    if provider in ("openai", "anthropic", "minimax"):
        model_prefix = "/chat/completions"
    elif provider == "gemini":
        model_prefix = "/models"
    else:
        model_prefix = "/api/chat"

    return base_url, model_prefix


async def stream_ollama(
    base_url: str, model: str, messages: list[dict], temperature: float
) -> AsyncGenerator[str, None]:
    """Stream chat from Ollama."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(
                f"{base_url}/api/chat",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": True,
                    "temperature": temperature,
                },
                timeout=120.0,
            )
            response.raise_for_status()

            async for line in response.aiter_lines():
                if line.strip():
                    yield f"data: {line}\n\n"

            yield "data: [DONE]\n\n"

        except httpx.HTTPError as e:
            yield f'data: {{"error": "Ollama connection failed: {str(e)}"}}\n\n'


async def stream_openai_compatible(
    base_url: str, model: str, messages: list[dict], temperature: float, max_tokens: Optional[int] = None, api_key: str = ""
) -> AsyncGenerator[str, None]:
    """Stream chat from OpenAI-compatible API (OpenAI, MiniMax, etc.)."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            payload = {
                "model": model,
                "messages": messages,
                "stream": True,
                "temperature": temperature,
            }
            if max_tokens:
                payload["max_tokens"] = max_tokens

            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            response = await client.post(
                f"{base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=120.0,
            )
            response.raise_for_status()

            async for line in response.aiter_lines():
                if line.strip() and not line.startswith(":"):
                    if line.startswith("data:"):
                        yield f"{line}\n\n"
                    else:
                        yield f"data: {line}\n\n"

            yield "data: [DONE]\n\n"

        except httpx.HTTPError as e:
            yield f'data: {{"error": "API connection failed: {str(e)}"}}\n\n'


async def stream_gemini(
    base_url: str, model: str, messages: list[dict], temperature: float, api_key: str = ""
) -> AsyncGenerator[str, None]:
    """Stream chat from Google Gemini API."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            gemini_contents = []
            for msg in messages:
                if msg["role"] == "user":
                    gemini_contents.append({"role": "user", "parts": [{"text": msg["content"]}]})
                elif msg["role"] == "assistant":
                    gemini_contents.append({"role": "model", "parts": [{"text": msg["content"]}]})
                elif msg["role"] == "system":
                    gemini_contents.append({"role": "user", "parts": [{"text": msg["content"]}]})

            payload = {
                "contents": gemini_contents,
                "generation_config": {
                    "temperature": temperature,
                }
            }

            headers = {}
            if api_key:
                headers["x-goog-api-key"] = api_key

            response = await client.post(
                f"{base_url}/models/{model}:generateContent",
                json=payload,
                headers=headers,
                timeout=120.0,
            )
            response.raise_for_status()
            data = response.json()

            if "candidates" in data:
                for candidate in data["candidates"]:
                    if "content" in candidate and "parts" in candidate["content"]:
                        for part in candidate["content"]["parts"]:
                            if "text" in part:
                                text = part["text"]
                                yield f'data: {{"choices": [{{"delta": {{"content": {json.dumps(text)}}}]}}\n\n'

            yield "data: [DONE]\n\n"

        except httpx.HTTPError as e:
            yield f'data: {{"error": "Gemini API connection failed: {str(e)}"}}\n\n'


async def stream_anthropic(
    base_url: str, model: str, messages: list[dict], temperature: float, max_tokens: Optional[int] = None
) -> AsyncGenerator[str, None]:
    """Stream chat from Anthropic Claude API."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            # Convert messages to Claude format
            # Anthropic uses system, user, assistant roles
            anthropic_messages = []
            system_prompt = ""
            for msg in messages:
                if msg["role"] == "system":
                    system_prompt = msg["content"]
                elif msg["role"] == "user":
                    anthropic_messages.append({"role": "user", "content": msg["content"]})
                elif msg["role"] == "assistant":
                    anthropic_messages.append({"role": "assistant", "content": msg["content"]})

            payload = {
                "model": model,
                "messages": anthropic_messages,
                "stream": True,
                "temperature": temperature,
            }
            if max_tokens:
                payload["max_tokens"] = max_tokens
            if system_prompt:
                payload["system"] = system_prompt

            # Anthropic streaming endpoint
            response = await client.post(
                f"{base_url}/v1/messages",
                json=payload,
                headers={
                    "x-api-key": os.getenv("ANTHROPIC_API_KEY", ""),
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                timeout=120.0,
            )
            response.raise_for_status()

            async for line in response.aiter_lines():
                if line.strip() and line.startswith("data:"):
                    yield f"{line}\n\n"

            yield "data: [DONE]\n\n"

        except httpx.HTTPError as e:
            yield f'data: {{"error": "Anthropic API connection failed: {str(e)}"}}\n\n'


def get_streaming_generator(
    provider: str, base_url: str, model: str, messages: list[dict], temperature: float, max_tokens: Optional[int] = None, api_key: Optional[str] = None
) -> AsyncGenerator[str, None]:
    """Get the appropriate streaming generator based on provider."""
    if provider == "ollama":
        return stream_ollama(base_url, model, messages, temperature)
    elif provider == "openai":
        return stream_openai_compatible(base_url, model, messages, temperature, max_tokens, api_key or OPENAI_API_KEY)
    elif provider == "minimax":
        return stream_openai_compatible(base_url, model, messages, temperature, max_tokens, api_key or MINIMAX_API_KEY)
    elif provider == "gemini":
        return stream_gemini(base_url, model, messages, temperature, api_key or GEMINI_API_KEY)
    elif provider == "anthropic":
        return stream_anthropic(base_url, model, messages, temperature, max_tokens)
    else:
        return stream_ollama(base_url, model, messages, temperature)


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest) -> StreamingResponse:
    provider = request.provider or "ollama"
    model = request.model or DEFAULT_MODEL
    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    base_url, _ = get_provider_config(provider, request.provider_base_url)

    if request.stream:
        return StreamingResponse(
            get_streaming_generator(provider, base_url, model, messages, request.temperature, request.max_tokens, request.api_key),
            media_type="text/event-stream",
        )

    # Non-streaming mode
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            if provider == "ollama":
                response = await client.post(
                    f"{base_url}/api/chat",
                    json={
                        "model": model,
                        "messages": messages,
                        "stream": False,
                        "temperature": request.temperature,
                    },
                    timeout=120.0,
                )
            elif provider == "openai" or provider == "minimax":
                payload = {
                    "model": model,
                    "messages": messages,
                    "temperature": request.temperature,
                }
                if request.max_tokens:
                    payload["max_tokens"] = request.max_tokens
                headers = {}
                api_key = request.api_key or (OPENAI_API_KEY if provider == "openai" else MINIMAX_API_KEY)
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                response = await client.post(
                    f"{base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=120.0,
                )
            elif provider == "gemini":
                gemini_contents = []
                for msg in messages:
                    if msg["role"] == "user":
                        gemini_contents.append({"role": "user", "parts": [{"text": msg["content"]}]})
                    elif msg["role"] == "assistant":
                        gemini_contents.append({"role": "model", "parts": [{"text": msg["content"]}]})
                headers = {}
                api_key = request.api_key or GEMINI_API_KEY
                if api_key:
                    headers["x-goog-api-key"] = api_key
                response = await client.post(
                    f"{base_url}/models/{model}:generateContent",
                    json={
                        "contents": gemini_contents,
                        "generation_config": {"temperature": request.temperature},
                    },
                    headers=headers,
                    timeout=120.0,
                )
            elif provider == "anthropic":
                anthropic_messages = []
                for msg in messages:
                    if msg["role"] == "user":
                        anthropic_messages.append({"role": "user", "content": msg["content"]})
                    elif msg["role"] == "assistant":
                        anthropic_messages.append({"role": "assistant", "content": msg["content"]})
                payload = {
                    "model": model,
                    "messages": anthropic_messages,
                    "temperature": request.temperature,
                }
                if request.max_tokens:
                    payload["max_tokens"] = request.max_tokens
                response = await client.post(
                    f"{base_url}/v1/messages",
                    json=payload,
                    headers={
                        "x-api-key": os.getenv("ANTHROPIC_API_KEY", ""),
                        "anthropic-version": "2023-06-01",
                    },
                    timeout=120.0,
                )
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

            response.raise_for_status()
            data = response.json()
            return StreamingResponse(
                iter([f'data: {json.dumps(data)}\n\n']),
                media_type="text/event-stream",
            )

        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Provider API failed: {str(e)}")


@app.post("/chat")
async def chat(request: ChatRequest) -> dict:
    provider = request.provider or "ollama"
    model = request.model or DEFAULT_MODEL
    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    base_url, _ = get_provider_config(provider, request.provider_base_url)

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            if provider == "ollama":
                response = await client.post(
                    f"{base_url}/api/chat",
                    json={
                        "model": model,
                        "messages": messages,
                        "stream": False,
                        "temperature": request.temperature,
                    },
                    timeout=120.0,
                )
            elif provider == "openai" or provider == "minimax":
                payload = {
                    "model": model,
                    "messages": messages,
                    "temperature": request.temperature,
                }
                if request.max_tokens:
                    payload["max_tokens"] = request.max_tokens
                headers = {}
                api_key = request.api_key or (OPENAI_API_KEY if provider == "openai" else MINIMAX_API_KEY)
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                response = await client.post(
                    f"{base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=120.0,
                )
            elif provider == "gemini":
                gemini_contents = []
                for msg in messages:
                    if msg["role"] == "user":
                        gemini_contents.append({"role": "user", "parts": [{"text": msg["content"]}]})
                    elif msg["role"] == "assistant":
                        gemini_contents.append({"role": "model", "parts": [{"text": msg["content"]}]})
                headers = {}
                api_key = request.api_key or GEMINI_API_KEY
                if api_key:
                    headers["x-goog-api-key"] = api_key
                response = await client.post(
                    f"{base_url}/models/{model}:generateContent",
                    json={
                        "contents": gemini_contents,
                        "generation_config": {"temperature": request.temperature},
                    },
                    headers=headers,
                    timeout=120.0,
                )
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

            response.raise_for_status()
            data = response.json()

            # Normalize response format
            if provider == "ollama":
                return {
                    "model": data.get("model", model),
                    "message": data.get("message", {}),
                    "done": data.get("done", True),
                }
            elif provider == "gemini":
                # Extract text from Gemini response
                text = ""
                if "candidates" in data:
                    for candidate in data["candidates"]:
                        if "content" in candidate and "parts" in candidate["content"]:
                            for part in candidate["content"]["parts"]:
                                if "text" in part:
                                    text += part["text"]
                return {
                    "model": model,
                    "message": {"role": "assistant", "content": text},
                    "done": True,
                }
            else:
                return {
                    "model": data.get("model", model),
                    "message": data.get("choices", [{}])[0].get("message", {}),
                    "done": True,
                }

        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Provider API failed: {str(e)}")


@app.get("/models")
async def list_models() -> dict:
    """List available models from Ollama."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Ollama connection failed: {str(e)}")


TAGGING_MODEL = settings.tagging_model

TAG_5W1H_PROMPT = """分析以下對話內容，提取 5W1H 標籤。
回覆必須是嚴格的 JSON 格式，包含以下欄位（值使用繁體中文，若無法判斷則填 "未知"）：
{
  "who": "涉及的人或角色",
  "what": "討論的主題或事項",
  "when": "涉及的時間",
  "where": "涉及的地點或範圍",
  "why": "目的或原因",
  "how": "方法或方式"
}

對話內容：
"""


def _build_tagging_messages(conversation: list[TaggingMessage]) -> list[dict[str, str]]:
    conversation_text = "\n".join(
        f"[{m.role}]: {m.content}" for m in conversation if m.content.strip()
    )
    return [
        {"role": "system", "content": "你是一個標籤提取助手，只輸出 JSON，不要輸出其他內容。"},
        {"role": "user", "content": f"{TAG_5W1H_PROMPT}{conversation_text}"},
    ]


def _parse_tags_response(raw: str) -> dict[str, str]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            parsed = json.loads(cleaned[start : end + 1])
        else:
            raise

    default_keys = ("who", "what", "when", "where", "why", "how")
    return {k: str(parsed.get(k, "未知")) for k in default_keys}


@app.post("/v1/chat/tag-5w1h", response_model=Tag5W1HResponse)
async def tag_5w1h(request: Tag5W1HRequest) -> Tag5W1HResponse:
    model = request.model or TAGGING_MODEL
    messages = _build_tagging_messages(request.messages)

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    "temperature": 0.3,
                },
            )
            response.raise_for_status()
            data = response.json()
            raw_content: str = data.get("message", {}).get("content", "")
        except httpx.HTTPError as e:
            raise HTTPException(
                status_code=502,
                detail=f"Ollama connection failed: {str(e)}",
            )

    try:
        tags = _parse_tags_response(raw_content)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("5W1H parse failed for session %s: %s | raw: %s", request.session_key, e, raw_content)
        tags = {k: "未知" for k in ("who", "what", "when", "where", "why", "how")}

    return Tag5W1HResponse(session_key=request.session_key, tags=tags)
