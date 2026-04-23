"""
@file        Tool executor implementations
@description Provides MCP, data agent, knowledge agent, and builtin executors.
@lastUpdate  2026-04-11 03:12:30
@author      AI Agent
@version     1.0.0
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from time import perf_counter

import httpx

from shared.tools.registry import ToolExecutionContext, ToolResult, ToolSource


def _auth_headers(context: ToolExecutionContext) -> dict[str, str]:
    headers = {
        "X-Trace-Id": context.trace_id,
        "X-Session-Id": context.session_id,
        "X-Handoff-Schema-Version": "2.0",
    }
    if context.auth_token:
        headers["Authorization"] = context.auth_token
    return headers


class BaseExecutor(ABC):
    def __init__(self, base_url: str = "", timeout_seconds: int = 30) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = float(timeout_seconds)

    @abstractmethod
    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, object],
        context: ToolExecutionContext,
    ) -> ToolResult:
        raise NotImplementedError


class MCPToolExecutor(BaseExecutor):
    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, object],
        context: ToolExecutionContext,
    ) -> ToolResult:
        start = perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(
                    f"{self._base_url}/execute",
                    json={
                        "tool": tool_name,
                        "params": arguments,
                        "parameters": arguments,
                        "context": {
                            "user_id": context.user_id,
                            "trace_id": context.trace_id,
                        },
                    },
                )
                response.raise_for_status()
                payload: object = response.json()
            return ToolResult(
                tool_name=tool_name,
                tool_call_id=context.correlation_id,
                success=True,
                result=payload,
                duration_ms=int((perf_counter() - start) * 1000),
                source=ToolSource.MCP,
                trace_id=context.trace_id,
            )
        except Exception as exc:
            return ToolResult(
                tool_name=tool_name,
                tool_call_id=context.correlation_id,
                success=False,
                result={},
                error=str(exc),
                duration_ms=int((perf_counter() - start) * 1000),
                source=ToolSource.MCP,
                trace_id=context.trace_id,
            )


class DataAgentExecutor(BaseExecutor):
    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, object],
        context: ToolExecutionContext,
    ) -> ToolResult:
        start = perf_counter()
        query_text = str(arguments.get("natural_language") or arguments.get("query") or "")
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(
                    f"{self._base_url}/query/query",
                    json={
                        "natural_language": query_text,
                        "context": {"tool_name": tool_name, "arguments": arguments},
                    },
                    headers=_auth_headers(context),
                )
                response.raise_for_status()
                payload: object = response.json()
            return ToolResult(
                tool_name=tool_name,
                tool_call_id=context.correlation_id,
                success=True,
                result=payload,
                duration_ms=int((perf_counter() - start) * 1000),
                source=ToolSource.DATA_AGENT,
                trace_id=context.trace_id,
            )
        except Exception as exc:
            return ToolResult(
                tool_name=tool_name,
                tool_call_id=context.correlation_id,
                success=False,
                result={},
                error=str(exc),
                duration_ms=int((perf_counter() - start) * 1000),
                source=ToolSource.DATA_AGENT,
                trace_id=context.trace_id,
            )


class KnowledgeAgentExecutor(BaseExecutor):
    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, object],
        context: ToolExecutionContext,
    ) -> ToolResult:
        start = perf_counter()
        query_text = str(arguments.get("query") or arguments.get("natural_language") or "")
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(
                    f"{self._base_url}/query",
                    json={"query": query_text, "limit": arguments.get("limit", 5)},
                    headers=_auth_headers(context),
                )
                if response.status_code == 404:
                    response = await client.post(
                        f"{self._base_url}/search",
                        json={"query": query_text, "limit": arguments.get("limit", 5)},
                        headers=_auth_headers(context),
                    )
                response.raise_for_status()
                payload: object = response.json()
            return ToolResult(
                tool_name=tool_name,
                tool_call_id=context.correlation_id,
                success=True,
                result=payload,
                duration_ms=int((perf_counter() - start) * 1000),
                source=ToolSource.KNOWLEDGE,
                trace_id=context.trace_id,
            )
        except Exception as exc:
            return ToolResult(
                tool_name=tool_name,
                tool_call_id=context.correlation_id,
                success=False,
                result={},
                error=str(exc),
                duration_ms=int((perf_counter() - start) * 1000),
                source=ToolSource.KNOWLEDGE,
                trace_id=context.trace_id,
            )


class BuiltinExecutor(BaseExecutor):
    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, object],
        context: ToolExecutionContext,
    ) -> ToolResult:
        del arguments
        start = perf_counter()
        try:
            result: object
            if tool_name == "current_time":
                result = {"timestamp": datetime.now(UTC).isoformat()}
            elif tool_name == "session_summary":
                result = {
                    "session_id": context.session_id,
                    "summary": "Session summary 尚未實作，後續版本補齊。",
                }
            else:
                raise ValueError(f"Unknown builtin tool: {tool_name}")
            return ToolResult(
                tool_name=tool_name,
                tool_call_id=context.correlation_id,
                success=True,
                result=result,
                duration_ms=int((perf_counter() - start) * 1000),
                source=ToolSource.BUILTIN,
                trace_id=context.trace_id,
            )
        except Exception as exc:
            return ToolResult(
                tool_name=tool_name,
                tool_call_id=context.correlation_id,
                success=False,
                result={},
                error=str(exc),
                duration_ms=int((perf_counter() - start) * 1000),
                source=ToolSource.BUILTIN,
                trace_id=context.trace_id,
            )
