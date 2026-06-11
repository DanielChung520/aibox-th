import json
import logging
import os
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:6500")
_req_id = 0


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str
    user_id: str | None = None
    agent_key: str | None = None


class ChatResponse(BaseModel):
    reply: str
    tool_calls: list[dict[str, Any]] = []


router = APIRouter(prefix="/mcp-gateway", tags=["MCP Gateway"])


async def _get_agent_config(agent_key: str) -> dict[str, Any] | None:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{GATEWAY_URL}/api/v1/agents/{agent_key}")
            if resp.status_code == 200:
                return resp.json().get("data")
    except Exception as e:
        logger.warning("Failed to fetch agent %s: %s", agent_key, e)
    return None


async def _mcp_jsonrpc(url, method, params=None, api_key=""):
    global _req_id
    _req_id += 1
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    body = {"jsonrpc": "2.0", "method": method, "id": f"r{_req_id}"}
    if params is not None:
        body["params"] = params
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.post(url, json=body, headers=headers)
        ct = r.headers.get("content-type", "")
        if "text/event-stream" in ct:
            result = None
            for line in r.text.splitlines():
                if line.startswith("data: "):
                    try:
                        d = json.loads(line[6:])
                        if "error" in d:
                            raise Exception(f"MCP error: {d['error'].get('message', d['error'])}")
                        return d.get("result")
                    except json.JSONDecodeError:
                        continue
            return result
        data = r.json()
        if "error" in data:
            raise Exception(f"MCP error: {data['error'].get('message', data['error'])}")
        return data.get("result")


async def _mcp_call_tool(url, tool_name, arguments, api_key=""):
    result = await _mcp_jsonrpc(url, "tools/call", {"name": tool_name, "arguments": arguments}, api_key)
    content = (result or {}).get("content", []) if result else []
    texts = [c["text"] for c in content if isinstance(c, dict) and c.get("type") == "text"]
    return "\n".join(texts) if texts else json.dumps(result, ensure_ascii=False)


async def _call_llm(endpoint, model, api_key, system_prompt, message, tools_desc):
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    prompt = (
        f"{message}\n\n可用工具:\n{tools_desc}\n\n"
        f"選擇工具並填參數。回覆格式: {{\"tool\": \"工具名\", \"arguments\": {{...}}}}"
        f"如果不需要工具就直接回覆用戶。"
    )
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt or "你是一個有用的助手。"},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=60.0) as c:
        r = await c.post(endpoint, json=body, headers=headers)
        r.raise_for_status()
        data = r.json()
    if "ollama" in endpoint:
        return (data.get("message") or {}).get("content", "")
    return ((data.get("choices", [{}])[0]).get("message") or {}).get("content", "")


@router.post("/chat", response_model=ChatResponse)
async def mcp_gateway_chat(req: ChatRequest) -> ChatResponse:
    if not req.agent_key:
        raise HTTPException(status_code=400, detail="agent_key is required")
    agent = await _get_agent_config(req.agent_key)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {req.agent_key} not found")

    mcp_url = (agent.get("mcp_url") or agent.get("endpoint_url") or "").rstrip("/")
    api_key = agent.get("api_key") or ""
    if not mcp_url:
        return ChatResponse(reply="請在 Agent 設定中指定 MCP URL")

    llm_mid = agent.get("llm_model", "")
    sp = agent.get("system_prompt", "")
    if not llm_mid:
        return ChatResponse(reply="請在 Agent 設定中指定 LLM 模型")

    from shared.llm_resolver import resolve as resolve_llm
    try:
        resolved = await resolve_llm(llm_mid)
        llm_cfg = {
            "endpoint": resolved.endpoint,
            "model_name": resolved.model_name,
            "api_key": resolved.api_key,
        }
    except Exception as e:
        return ChatResponse(reply=f"無法解析 LLM 模型: {e}")

    try:
        # Step 1: Discover tools via MCP JSON-RPC
        tools_result = await _mcp_jsonrpc(mcp_url, "tools/list", api_key=api_key)
        tools = (tools_result or {}).get("tools", []) if isinstance(tools_result, dict) else (tools_result or [])
        if not tools:
            return ChatResponse(reply="MCP Server 已連線，但沒有提供任何工具。")
    except Exception as e:
        logger.error("MCP tools/list failed: %s", e)
        return ChatResponse(reply=f"無法連接到 MCP Server ({mcp_url}): {e}")

    tools_desc = "\n".join(f"- {t.get('name')}: {t.get('description', '')}" for t in tools)

    # Step 2: LLM decides which tool to call
    llm_resp = await _call_llm(llm_cfg["endpoint"], llm_cfg["model_name"],
                                llm_cfg.get("api_key", ""), sp, req.message or "", tools_desc)

    try:
        decision = json.loads(llm_resp)
    except json.JSONDecodeError:
        return ChatResponse(reply=llm_resp)

    tool_name = decision.get("tool", "")
    arguments = decision.get("arguments", {})
    if not tool_name:
        return ChatResponse(reply=llm_resp)

    if not any(t["name"] == tool_name for t in tools):
        names = ", ".join(t["name"] for t in tools)
        return ChatResponse(reply=f"工具 '{tool_name}' 不存在。可用工具: {names}")

    # Step 3: Execute tool
    try:
        result_text = await _mcp_call_tool(mcp_url, tool_name, arguments, api_key)
    except Exception as e:
        logger.error("MCP tools/call failed: %s", e)
        return ChatResponse(reply=f"工具執行失敗: {e}")

    # Step 4: LLM summarizes the result
    summary = await _call_llm(
        llm_cfg["endpoint"], llm_cfg["model_name"], llm_cfg.get("api_key", ""), sp,
        f"用戶要求: {req.message}\n\n工具 {tool_name} 結果:\n{result_text}\n\n請用繁體中文回覆用戶。",
        "",
    )
    return ChatResponse(reply=summary or result_text)
