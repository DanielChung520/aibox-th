"""
@file        Tool executor node
@description Executes tool calls using shared/tools/ registry and appends results to state.
@lastUpdate  2026-04-21 10:00:00
@author      Daniel Chung
@version     1.0.0
"""

import json
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage

from shared.orchestration.state import AgentState
from shared.tools import ToolExecutionContext, ToolRegistry

_REGISTRY: ToolRegistry | None = None
_MCP_URL: str | None = None
_DA_URL: str | None = None
_KA_URL: str | None = None


async def _get_registry() -> ToolRegistry:
    global _REGISTRY, _MCP_URL, _DA_URL, _KA_URL
    if _REGISTRY is None:
        mcp = _MCP_URL or "http://localhost:8004"
        da = _DA_URL or "http://localhost:8003"
        ka = _KA_URL or "http://localhost:8007"
        _REGISTRY = ToolRegistry()
        await _REGISTRY.initialize(mcp, da, ka)
    return _REGISTRY


def configure(mcp_tools_url: str, data_agent_url: str, knowledge_agent_url: str) -> None:
    global _MCP_URL, _DA_URL, _KA_URL, _REGISTRY
    _MCP_URL = mcp_tools_url
    _DA_URL = data_agent_url
    _KA_URL = knowledge_agent_url
    _REGISTRY = None


def _parse_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _call_name(call: dict[str, Any]) -> str:
    if isinstance(call.get("name"), str):
        return call["name"]
    func = call.get("function", {})
    if isinstance(func, dict) and isinstance(func.get("name"), str):
        return str(func["name"])
    return ""


def _call_id(call: dict[str, Any], fallback: str) -> str:
    val = call.get("id")
    return str(val) if val else fallback


def _format_result(result: Any) -> str:
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception:
        return str(result)


async def tool_executor_node(state: AgentState) -> dict[str, Any]:
    last_message = state["messages"][-1] if state["messages"] else None
    if not isinstance(last_message, AIMessage):
        return {"tool_results": [], "state_version": state["state_version"] + 1}

    tool_calls_attr = getattr(last_message, "tool_calls", None)
    if isinstance(tool_calls_attr, list):
        raw_calls = [c for c in tool_calls_attr if isinstance(c, dict)]
    else:
        extra = last_message.additional_kwargs.get("tool_calls", [])
        raw_calls = [c for c in extra if isinstance(c, dict)] if isinstance(extra, list) else []

    if not raw_calls:
        return {"tool_results": [], "state_version": state["state_version"] + 1}

    registry = await _get_registry()
    tool_messages: list[ToolMessage] = []
    tool_results_list: list[dict[str, Any]] = []

    for i, call in enumerate(raw_calls, start=1):
        tool_name = _call_name(call)
        call_id = _call_id(call, f"tool-call-{i}")
        arguments = _parse_arguments(call.get("arguments") or call.get("function", {}).get("arguments", {}))

        context = ToolExecutionContext(
            user_id=state["user_id"],
            session_id=state["session_id"],
            trace_id=f"{state['session_id']}-{state['state_version']}-{call_id}",
            auth_token="",
            correlation_id=call_id,
        )

        try:
            result = await registry.execute(tool_name, arguments, context)
            tool_messages.append(ToolMessage(content=_format_result(result.result), tool_call_id=call_id))
            tool_results_list.append({
                "tool_name": tool_name,
                "success": result.success,
                "result": result.result,
                "error": result.error,
                "source": result.source.value,
                "duration_ms": result.duration_ms,
            })
        except Exception as exc:
            tool_messages.append(ToolMessage(content=f"{{\"error\": \"{exc}\"}}", tool_call_id=call_id))
            tool_results_list.append({
                "tool_name": tool_name,
                "success": False,
                "result": {},
                "error": str(exc),
            })

    existing = state.get("tool_results", [])
    return {
        "messages": tool_messages,
        "tool_results": existing + tool_results_list,
        "state_version": state["state_version"] + 1,
    }