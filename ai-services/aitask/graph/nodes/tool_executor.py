"""
@file        Tool executor node
@description Executes tool calls emitted by the LLM and appends ToolMessage outputs.
@lastUpdate  2026-04-11 03:12:30
@author      AI Agent
@version     1.0.0
"""

from __future__ import annotations

import json

from langchain_core.messages import AIMessage, ToolMessage

from aitask.config import settings
from aitask.graph.state import TopState
from aitask.tools.registry import ToolExecutionContext, ToolRegistry, ToolResult

_TOOL_REGISTRY: ToolRegistry | None = None


async def _get_registry() -> ToolRegistry:
    global _TOOL_REGISTRY
    if _TOOL_REGISTRY is None:
        _TOOL_REGISTRY = ToolRegistry()
        await _TOOL_REGISTRY.initialize(settings.services)
    return _TOOL_REGISTRY


def _extract_tool_calls(message: AIMessage) -> list[dict[str, object]]:
    tool_calls = getattr(message, "tool_calls", None)
    if isinstance(tool_calls, list):
        return [call for call in tool_calls if isinstance(call, dict)]
    extra = message.additional_kwargs.get("tool_calls", [])
    return [call for call in extra if isinstance(call, dict)] if isinstance(extra, list) else []


def _tool_arguments(tool_call: dict[str, object]) -> dict[str, object]:
    args = tool_call.get("args")
    if isinstance(args, dict):
        return args
    function_obj = tool_call.get("function")
    if isinstance(function_obj, dict):
        raw_arguments = function_obj.get("arguments")
        if isinstance(raw_arguments, str):
            try:
                parsed = json.loads(raw_arguments)
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                return {}
    return {}


def _tool_name(tool_call: dict[str, object]) -> str:
    name = tool_call.get("name")
    if isinstance(name, str):
        return name
    function_obj = tool_call.get("function")
    if isinstance(function_obj, dict) and isinstance(function_obj.get("name"), str):
        return str(function_obj["name"])
    return ""


def _tool_call_id(tool_call: dict[str, object], fallback: str) -> str:
    value = tool_call.get("id")
    return str(value) if value else fallback


def _tool_message_content(result: ToolResult) -> str:
    payload: object = result.result if result.success else {"error": result.error or "tool execution failed"}
    return payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, default=str)


async def tool_executor_node(state: TopState) -> dict[str, object]:
    last_message = state["messages"][-1]
    if not isinstance(last_message, AIMessage):
        return {"tool_results": []}

    registry = await _get_registry()
    tool_messages: list[ToolMessage] = []
    tool_results: list[dict[str, object]] = []

    for index, tool_call in enumerate(_extract_tool_calls(last_message), start=1):
        tool_name = _tool_name(tool_call)
        tool_call_id = _tool_call_id(tool_call, f"tool-call-{index}")
        context = ToolExecutionContext(
            user_id=state["user_id"],
            session_id=state["session_id"],
            trace_id=f"{state['session_id']}-{state['state_version']}-{tool_call_id}",
            auth_token="",
            correlation_id=tool_call_id,
        )
        result = await registry.execute(tool_name, _tool_arguments(tool_call), context)
        tool_messages.append(
            ToolMessage(content=_tool_message_content(result), tool_call_id=tool_call_id)
        )
        tool_results.append(result.model_dump())

    return {
        "messages": tool_messages,
        "tool_results": tool_results,
        "state_version": state["state_version"] + 1,
    }
