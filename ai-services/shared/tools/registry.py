"""
@file        Tool registry models and service
@description Defines tool metadata, execution context, and tool discovery/dispatch.
             This is the standard tool orchestration layer for all agents.
@lastUpdate  2026-04-21 10:00:00
@author      Daniel Chung
@version     1.0.0
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any

import httpx
from pydantic import BaseModel

if TYPE_CHECKING:
    from shared.tools.executors import BaseExecutor


class ToolSource(str, Enum):
    MCP = "mcp"
    DATA_AGENT = "data_agent"
    KNOWLEDGE = "knowledge"
    BUILTIN = "builtin"
    BPA = "bpa"


class ToolDefinition(BaseModel):
    name: str
    description: str
    source: ToolSource
    parameters: dict[str, Any]
    requires_auth: bool = True
    timeout_seconds: int = 30
    mcp_endpoint: str | None = None
    category: str = "general"
    version: str = "1.0.0"


class ToolResult(BaseModel):
    tool_name: str
    tool_call_id: str
    success: bool
    result: Any
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


def _json_schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
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

    async def initialize(
        self,
        mcp_tools_url: str,
        data_agent_url: str,
        knowledge_agent_url: str,
        auth_token: str = "",
    ) -> None:
        from shared.tools.executors import (
            BuiltinExecutor,
            DataAgentExecutor,
            KnowledgeAgentExecutor,
            MCPToolExecutor,
        )

        self._tools.clear()
        self._executors = {
            ToolSource.MCP: MCPToolExecutor(mcp_tools_url),
            ToolSource.DATA_AGENT: DataAgentExecutor(data_agent_url),
            ToolSource.KNOWLEDGE: KnowledgeAgentExecutor(knowledge_agent_url),
            ToolSource.BUILTIN: BuiltinExecutor(),
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(f"{mcp_tools_url.rstrip('/')}/tools")
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
                        mcp_endpoint=f"{mcp_tools_url.rstrip('/')}/execute",
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
        self._register(
            ToolDefinition(
                name="local_tts",
                description="將逐字稿或文字內容轉為本地 WAV 語音，支援多聲線樣本輸出。",
                source=ToolSource.BUILTIN,
                parameters=_json_schema(
                    {
                        "text": {"type": "string", "description": "要轉語音的文字內容"},
                        "file_path": {"type": "string", "description": "輸入文字檔或逐字稿路徑"},
                        "output_path": {"type": "string", "description": "單一語音輸出路徑，或 sample_voices 模式下的輸出目錄"},
                        "voice_seed": {"type": "integer", "description": "固定音色的 speaker seed"},
                        "sample_voices": {"type": "boolean", "description": "是否輸出多個聲線樣本"},
                        "sample_text": {"type": "string", "description": "多聲線樣本專用文字，未填則沿用 text 或 file_path 內容"},
                        "voice_seeds": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "sample_voices 模式使用的 speaker seed 清單",
                        },
                        "paragraph_pause_ms": {"type": "integer", "description": "段落間預設停頓毫秒數"},
                        "max_chars_per_chunk": {"type": "integer", "description": "單段最大字數，超過會自動切段"},
                    },
                    ["output_path"],
                ),
                category="builtin",
            )
        )

        self._register(
            ToolDefinition(
                name="multimedia_analyzer",
                description="Upload and analyze image/video using AI vision models, transcribe audio. Backs up original to SeaweedFS.",
                source=ToolSource.BUILTIN,
                parameters=_json_schema(
                    {
                        "content_b64": {"type": "string", "description": "Base64-encoded media content"},
                        "media_type": {"type": "string", "enum": ["image", "video", "audio"], "description": "Type of media to analyze"},
                        "filename": {"type": "string", "description": "Original filename"},
                        "platform": {"type": "string", "description": "Source platform (line, whatsapp, etc.)"},
                        "user_id": {"type": "string", "description": "User identifier for storage path"},
                        "mime_type": {"type": "string", "description": "MIME type of the content"},
                        "prompt": {"type": "string", "description": "Custom prompt for analysis (optional)"},
                    },
                    ["content_b64", "media_type"],
                ),
                category="builtin",
            )
        )

        self._register(
            ToolDefinition(
                name="query_preorder_items",
                description="查詢預購可用之品項（品名、規格、庫存數量、單位），用於前置詢價或建立預購單。技能編號：SKL-2618-002。",
                source=ToolSource.BUILTIN,
                parameters=_json_schema(
                    {
                        "session_id": {"type": "string", "description": "對話 session 識別碼"},
                        "user_id": {"type": "string", "description": "使用者識別碼"},
                        "filter_term": {"type": "string", "description": "篩選關鍵字（品名含該字才回傳）"},
                    },
                    ["session_id", "user_id"],
                ),
                requires_auth=False,
                category="bpa",
            )
        )

    def get_tools_for_llm(self) -> list[dict[str, Any]]:
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
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> ToolResult:
        definition = self._tools.get(tool_name)
        if definition is None:
            raise ValueError(f"Unknown tool: {tool_name}")
        executor = self._executors.get(definition.source)
        if executor is None:
            raise ValueError(f"No executor registered for tool source: {definition.source}")
        return await executor.execute(tool_name, arguments, context)
