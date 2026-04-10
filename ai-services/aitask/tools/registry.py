"""
@file        Tool registry models and service
@description Defines tool metadata, execution context, and tool discovery/dispatch.
@lastUpdate  2026-04-11 03:12:30
@author      AI Agent
@version     1.0.0
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

import httpx
from pydantic import BaseModel

from aitask.config import ServiceConfig

if TYPE_CHECKING:
    from aitask.tools.executors import BaseExecutor


class ToolSource(str, Enum):
    MCP = "mcp"
    DATA_AGENT = "data_agent"
    KNOWLEDGE = "knowledge"
    BUILTIN = "builtin"


class ToolDefinition(BaseModel):
    name: str
    description: str
    source: ToolSource
    parameters: dict[str, object]
    requires_auth: bool = True
    timeout_seconds: int = 30
    mcp_endpoint: str | None = None
    category: str = "general"
    version: str = "1.0.0"


class ToolResult(BaseModel):
    tool_name: str
    tool_call_id: str
    success: bool
    result: object
    error: str | None = None
    duration_ms: int = 0
    source: ToolSource
    trace_id: str | None = None


class ToolExecutionContext(BaseModel):
    user_id: str
    session_id: str
    trace_id: str
    auth_token: str
    correlation_id: str


def _json_schema(properties: dict[str, object], required: list[str] | None = None) -> dict[str, object]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
    }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._executors: dict[ToolSource, BaseExecutor] = {}

    def _register(self, definition: ToolDefinition) -> None:
        self._tools[definition.name] = definition

    async def initialize(self, services_config: ServiceConfig) -> None:
        from aitask.tools.executors import (
            BuiltinExecutor,
            DataAgentExecutor,
            KnowledgeAgentExecutor,
            MCPToolExecutor,
        )

        self._tools.clear()
        self._executors = {
            ToolSource.MCP: MCPToolExecutor(services_config.mcp_tools_url),
            ToolSource.DATA_AGENT: DataAgentExecutor(services_config.data_agent_url),
            ToolSource.KNOWLEDGE: KnowledgeAgentExecutor(services_config.knowledge_agent_url),
            ToolSource.BUILTIN: BuiltinExecutor(),
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(f"{services_config.mcp_tools_url.rstrip('/')}/tools")
            response.raise_for_status()
            payload = response.json()
        raw_tools = payload.get("tools", {}) if isinstance(payload, dict) else {}
        if isinstance(raw_tools, dict):
            for tool_name, raw_tool in raw_tools.items():
                if not isinstance(raw_tool, dict):
                    continue
                raw_parameters = raw_tool.get("parameters", {})
                properties = raw_parameters if isinstance(raw_parameters, dict) else {}
                self._register(
                    ToolDefinition(
                        name=str(tool_name),
                        description=str(raw_tool.get("description", "")),
                        source=ToolSource.MCP,
                        parameters=_json_schema(properties),
                        mcp_endpoint=f"{services_config.mcp_tools_url.rstrip('/')}/execute",
                        category="mcp",
                    )
                )

        self._register(
            ToolDefinition(
                name="da_query",
                description="查詢資料代理服務並回傳結構化結果。",
                source=ToolSource.DATA_AGENT,
                parameters=_json_schema(
                    {
                        "query": {"type": "string", "description": "自然語言查詢內容"},
                        "natural_language": {"type": "string", "description": "自然語言查詢內容"},
                    },
                    ["query"],
                ),
                category="data",
            )
        )
        self._register(
            ToolDefinition(
                name="da_visualize",
                description="請資料代理生成視覺化所需資料。",
                source=ToolSource.DATA_AGENT,
                parameters=_json_schema({"query": {"type": "string"}}, ["query"]),
                category="data",
            )
        )
        self._register(
            ToolDefinition(
                name="ka_search",
                description="查詢知識代理進行 RAG 檢索。",
                source=ToolSource.KNOWLEDGE,
                parameters=_json_schema({"query": {"type": "string"}}, ["query"]),
                category="knowledge",
            )
        )
        self._register(
            ToolDefinition(
                name="ka_doc_retrieve",
                description="擷取知識庫文件內容。",
                source=ToolSource.KNOWLEDGE,
                parameters=_json_schema({"query": {"type": "string"}}, ["query"]),
                category="knowledge",
            )
        )
        self._register(
            ToolDefinition(
                name="current_time",
                description="取得目前 UTC 時間。",
                source=ToolSource.BUILTIN,
                parameters=_json_schema({}),
                requires_auth=False,
                category="builtin",
            )
        )
        self._register(
            ToolDefinition(
                name="session_summary",
                description="取得目前 session 摘要。",
                source=ToolSource.BUILTIN,
                parameters=_json_schema({}),
                category="builtin",
            )
        )

    def get_tools_for_llm(self) -> list[dict[str, object]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": definition.name,
                    "description": definition.description,
                    "parameters": definition.parameters,
                },
            }
            for definition in self._tools.values()
        ]

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, object],
        context: ToolExecutionContext,
    ) -> ToolResult:
        definition = self._tools.get(tool_name)
        if definition is None:
            raise ValueError(f"Unknown tool: {tool_name}")
        executor = self._executors.get(definition.source)
        if executor is None:
            raise ValueError(f"No executor registered for tool source: {definition.source}")
        return await executor.execute(tool_name, arguments, context)
