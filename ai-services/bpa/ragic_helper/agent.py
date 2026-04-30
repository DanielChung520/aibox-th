import os
from typing import Any, cast

import httpx
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
INTENT_RAG_URL = os.getenv("INTENT_RAG_URL", "http://localhost:8011/da/intent-rag")
HYBRID_RAG_URL = os.getenv("HYBRID_RAG_URL", "http://localhost:8011/ka/hybrid")
MCP_TOOLS_URL = os.getenv("MCP_TOOLS_URL", "http://localhost:8004")
DATA_AGENT_URL = os.getenv("DATA_AGENT_URL", "http://localhost:8003")
KNOWLEDGE_AGENT_URL = os.getenv("KNOWLEDGE_AGENT_URL", "http://localhost:8007")


async def detect_intent(query: str, scope: str = "data_agent") -> dict | None:
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{INTENT_RAG_URL}/{scope}/intent/match",
                json={"query": query, "top_k": 3},
            )
            if resp.status_code == 200:
                data = resp.json()
                best = data.get("best_match")
                if best and best.get("score", 0) > 0.5:
                    return best
        except Exception:
            pass
    return None


async def hybrid_search(
    query: str, collection: str = "knowledge_default", top_k: int = 5
) -> list[dict]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{HYBRID_RAG_URL}/search",
                json={
                    "query": query,
                    "collection": collection,
                    "top_k": top_k,
                    "strategy": "hybrid",
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("results", [])
        except Exception:
            pass
    return []


async def build_rag_context(intents: list[dict], query: str) -> str:
    context_parts = []

    if intents:
        context_parts.append("## 匹配的意圖")
        for intent in intents[:3]:
            intent_data = intent.get("intent_data", {})
            name = intent_data.get("name", "")
            description = intent_data.get("description", "")
            action = intent_data.get("action", "")
            if name:
                context_parts.append(f"- **{name}**: {description}")
            if action:
                context_parts.append(f"  操作: {action}")

    rag_results = await hybrid_search(query, top_k=5)
    if rag_results:
        context_parts.append("\n## 相關知識")
        for i, result in enumerate(rag_results[:5], 1):
            content = result.get("content", "")[:500]
            source = result.get("source", "unknown")
            context_parts.append(f"{i}. [{source}]\n   {content}...")

    return "\n".join(context_parts) if context_parts else ""


async def call_llm_chat(
    messages: list[dict],
    model: str,
    api_base: str | None = None,
    api_key: str = "",
    temperature: float = 0.7,
    max_tokens: int = 2000,
    images: list[str] | None = None,
    tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    base = api_base or OLLAMA_BASE_URL
    is_local = "localhost" in base or "127.0.0.1" in base

    if is_local:
        return await _call_ollama_chat(
            model, messages, base, temperature, max_tokens, images, tools
        )

    return await _call_openai_compatible_chat(
        model, messages, base, api_key, temperature, max_tokens, tools
    )


async def _call_ollama_chat(
    model: str,
    messages: list[dict],
    base_url: str,
    temperature: float,
    max_tokens: int,
    images: list[str] | None,
    tools: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    if images:
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                prompt_parts.append(f"[系統]: {content}")
            elif role == "user":
                prompt_parts.append(f"[用戶]: {content}")
            else:
                prompt_parts.append(f"[助理]: {content}")
        full_prompt = "\n".join(prompt_parts)
        payload = {
            "model": model,
            "prompt": full_prompt,
            "images": images,
            "stream": False,
            "temperature": temperature,
            "options": {"num_predict": max_tokens},
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{base_url}/api/generate", json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = data.get("response", "") or data.get("thinking", "")
            return {"message": {"role": "assistant", "content": content}}

    chat_payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "temperature": temperature,
        "options": {"num_predict": max_tokens},
    }
    if tools:
        chat_payload["tools"] = tools

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(f"{base_url}/api/chat", json=chat_payload)
        resp.raise_for_status()
        return resp.json()


async def _call_openai_compatible_chat(
    model: str,
    messages: list[dict],
    base_url: str,
    api_key: str,
    temperature: float,
    max_tokens: int,
    tools: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        payload["tools"] = tools

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{base_url}/chat/completions", json=payload, headers=headers
        )
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")
            if content:
                return {"message": {"role": "assistant", "content": content}}
        return {"message": {"role": "assistant", "content": ""}}


def _conversation_history_to_messages(
    history: list[dict],
) -> list[AIMessage | HumanMessage]:
    msgs: list[AIMessage | HumanMessage] = []
    for entry in history:
        role = entry.get("role", "user")
        content = entry.get("content", "")
        if role == "assistant":
            msgs.append(AIMessage(content=content))
        else:
            msgs.append(HumanMessage(content=content))
    return msgs


def _message_to_dict(
    message: AIMessage | HumanMessage | SystemMessage,
) -> dict[str, str]:
    msg_type = message.type
    role = "user" if msg_type == "human" else msg_type
    raw_content = message.content
    content_str = raw_content if isinstance(raw_content, str) else str(raw_content)
    return {"role": role, "content": content_str}


async def chat_with_agent(
    query: str,
    session_id: str,
    agent_config: dict,
    conversation_history: list[dict],
    images: list[str] | None = None,
    user_id: str = "anonymous",
    max_tool_loops: int = 3,
) -> str:
    system_prompt = agent_config.get(
        "system_prompt",
        "你是 Ragic 系統的 AI 助理，專門回答關於 Ragic 操作的問題。",
    )

    intents = await detect_intent(query, scope="data_agent")

    rag_context = await build_rag_context([intents] if intents else [], query)

    if rag_context:
        system_with_context = f"""{system_prompt}

## 參考資訊
{rag_context}
"""
    else:
        system_with_context = system_prompt

    messages = [{"role": "system", "content": system_with_context}]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": query})

    model = agent_config.get("model", "llama3.2:latest")
    if images:
        model = "qwen3-vl:latest"
    temperature = agent_config.get("temperature", 0.7)
    max_tokens = agent_config.get("max_tokens", 2000)
    api_base = agent_config.get("api_base")
    api_key = agent_config.get("api_key", "")
    tools = agent_config.get("tools", [])
    content = ""

    if not tools:
        response_data = await call_llm_chat(
            messages=messages,
            model=model,
            api_base=api_base,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            images=images,
        )
        return response_data.get("message", {}).get("content", "")

    from shared.orchestration.nodes.tool_executor import tool_executor_node
    from shared.orchestration.state import AgentState

    seed = _conversation_history_to_messages(conversation_history)
    state_messages: list[AIMessage | HumanMessage | SystemMessage] = (
        [SystemMessage(content=system_with_context)]
        + seed
        + [HumanMessage(content=query)]
    )
    tool_results_accumulated: list[dict[str, Any]] = []
    state_version = 0

    for loop_idx in range(max_tool_loops):
        response_data = await call_llm_chat(
            messages=[_message_to_dict(m) for m in state_messages],
            model=model,
            api_base=api_base,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            images=images if loop_idx == 0 else None,
            tools=tools if loop_idx == 0 else None,
        )
        images = None

        assistant_msg = response_data.get("message", {})
        content = assistant_msg.get("content", "")

        tool_calls = response_data.get("tool_calls") or assistant_msg.get(
            "tool_calls", []
        )

        if not tool_calls:
            return content

        tool_state: dict[str, Any] = {
            "session_id": session_id,
            "user_id": user_id,
            "messages": [AIMessage(content=content)],
            "state_version": state_version,
            "tool_results": tool_results_accumulated,
            "pending_tool_calls": [],
            "extra": {},
        }
        executor_result = await tool_executor_node(cast(AgentState, tool_state))
        state_version = executor_result.get("state_version", state_version + 1)
        new_results = executor_result.get("tool_results", [])
        tool_results_accumulated = tool_results_accumulated + new_results

        tool_msgs = executor_result.get("messages", [])
        state_messages = state_messages + [AIMessage(content=content)] + tool_msgs

    final_response = await call_llm_chat(
        messages=[_message_to_dict(m) for m in state_messages],
        model=model,
        api_base=api_base,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return final_response.get("message", {}).get("content", "") or content
