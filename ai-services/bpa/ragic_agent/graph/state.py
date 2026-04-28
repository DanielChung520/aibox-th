"""
@file        Ragic Agent — Graph State
@description 擴展 AgentState，加入 Ragic 專用欄位
@lastUpdate  2026-04-27 19:30:00
@author      AI Agent
@version     1.0.0
"""

from typing import Literal, Optional

from shared.orchestration.state import AgentState


class RagicState(AgentState):
    """Ragic Agent 專用狀態。"""
    action_plan: str = "direct_answer"
    current_intent: Optional[str] = None
    intent_confidence: float = 0.0
    intent_method: Literal["rule", "llm"] = "rule"
    matched_intent_data: Optional[dict[str, object]] = None
    coreference_resolved: bool = False
    context_entities: dict[str, str] = {}
    complaint_detected: bool = False
