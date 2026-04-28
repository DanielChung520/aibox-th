"""
@file        Tool executor implementations
@description Provides MCP, data agent, knowledge agent, and builtin executors.
             Used by ToolRegistry to execute tools from any agent.
@lastUpdate  2026-04-21 10:00:00
@author      Daniel Chung
@version     1.0.0
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx

from shared.tools.registry import ToolExecutionContext, ToolResult, ToolSource
from tools.local_tts.local_tts_tool import LocalTTSInput, LocalTTSTool


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
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> ToolResult:
        raise NotImplementedError


class MCPToolExecutor(BaseExecutor):
    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
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
        arguments: dict[str, Any],
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
        arguments: dict[str, Any],
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
    def __init__(self, base_url: str = "", timeout_seconds: int = 30) -> None:
        super().__init__(base_url=base_url, timeout_seconds=timeout_seconds)
        self._local_tts_tool = LocalTTSTool()
        self._multimedia_tool: Any = None

    def _get_multimedia_tool(self):
        if self._multimedia_tool is None:
            from tools.multimedia_analyzer import MultimediaAnalyzerTool
            self._multimedia_tool = MultimediaAnalyzerTool()
        return self._multimedia_tool

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> ToolResult:
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
            elif tool_name == "local_tts":
                payload = self._normalize_local_tts_arguments(arguments, context)
                tool_output = await self._local_tts_tool.execute(LocalTTSInput(**payload))
                result = tool_output.model_dump()
            elif tool_name == "multimedia_analyzer":
                from tools.multimedia_analyzer import MultimediaAnalyzerInput
                vision_model = arguments.get("vision_model") or None
                if not vision_model:
                    vision_model = await self._lookup_tool_model("multimedia-analyzer")
                inp = MultimediaAnalyzerInput(
                    content_b64=arguments.get("content_b64", ""),
                    media_type=arguments.get("media_type", "image"),
                    filename=arguments.get("filename", "unnamed"),
                    platform=arguments.get("platform", context.session_id),
                    user_id=arguments.get("user_id", context.user_id or "agent"),
                    mime_type=arguments.get("mime_type", "application/octet-stream"),
                    prompt=arguments.get("prompt"),
                    vision_model=vision_model,
                )
                tool = self._get_multimedia_tool()
                output = await tool.execute(inp)
                result = output.model_dump()
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

    async def _lookup_tool_endpoint(self, tool_code: str) -> str | None:
        try:
            import os, base64
            cred = f"{os.getenv('ARANGO_USER','root')}:{os.getenv('ARANGO_PASSWORD','')}"
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    f"{os.getenv('ARANGO_URL','http://localhost:8529')}/_db/{os.getenv('ARANGO_DATABASE','abc_desktop')}/_api/cursor",
                    json={"query": "FOR t IN tools FILTER t.code == @code LIMIT 1 RETURN t.endpoint_url", "bindVars": {"code": tool_code}},
                    headers={"Content-Type": "application/json", "Authorization": f"Basic {base64.b64encode(cred.encode()).decode()}"},
                )
                if resp.status_code in (200, 201):
                    rows = resp.json().get("result", [])
                    if rows and rows[0]:
                        return rows[0]
        except Exception:
            pass
        return None

    async def _lookup_tool_model(self, tool_code: str) -> str | None:
        try:
            import os, base64
            cred = f"{os.getenv('ARANGO_USER','root')}:{os.getenv('ARANGO_PASSWORD','')}"
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    f"{os.getenv('ARANGO_URL','http://localhost:8529')}/_db/{os.getenv('ARANGO_DATABASE','abc_desktop')}/_api/cursor",
                    json={"query": "FOR t IN tools FILTER t.code == @code LIMIT 1 RETURN t.llm_model", "bindVars": {"code": tool_code}},
                    headers={"Content-Type": "application/json", "Authorization": f"Basic {base64.b64encode(cred.encode()).decode()}"},
                )
                if resp.status_code in (200, 201):
                    rows = resp.json().get("result", [])
                    if rows and rows[0]:
                        return rows[0]
        except Exception:
            pass
        return None

    def _normalize_local_tts_arguments(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        payload = dict(arguments)
        output_path = payload.get("output_path")
        if not output_path:
            output_dir = Path("/Users/daniel/GitHub/AIBox/ai-services/.tmp/tts")
            output_dir.mkdir(parents=True, exist_ok=True)
            suffix = "samples" if payload.get("sample_voices") else f"{context.session_id}_{context.correlation_id}.wav"
            payload["output_path"] = str(output_dir / suffix)
        return payload
