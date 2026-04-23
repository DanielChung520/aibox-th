"""
Models for TopIntentRAG.

# Last Update: 2026-04-14
# Author: AI Agent
# Version: 1.0.0
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    DIRECT_ANSWER = "direct_answer"
    TOOL_CALL = "tool_call"
    PROCESS_ORCHESTRATION = "process_orchestration"


class TargetAgent(str, Enum):
    CHAT = "chat"
    TOOL = "tool"
    PDCA = "pdca"
    BPA = "bpa"
    CA = "ca"


class ToolCategory(str, Enum):
    WEB_SEARCH = "web_search"
    DATA = "data"
    KNOWLEDGE = "knowledge"
    MCP = "mcp"


class TopIntentMatchResult(BaseModel):
    intent_id: str
    score: float
    name: str
    description: str
    intent_type: str
    domain: str
    action_type: Optional[str] = None
    target_agent: Optional[str] = None
    tool_category: Optional[str] = None
    tool_name: Optional[str] = None
    bpa_id: Optional[str] = None
    pdca_id: Optional[str] = None
    ca_id: Optional[str] = None
    response_strategy: Optional[str] = None
    confidence_threshold: float = 0.7
    source: str = "hybrid"


class TopIntentMatchResponse(BaseModel):
    query: str
    matches: list[TopIntentMatchResult] = Field(default_factory=list)
    best_match: Optional[TopIntentMatchResult] = None
    multi_intent: dict[str, object] = Field(default_factory=dict)
    reasoning: str = ""


class EmbedSyncResponse(BaseModel):
    synced_count: int
    collection: str
    status: str