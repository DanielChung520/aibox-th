"""
@file        訂單小秘 — Graph State（預留 LangGraph 擴展）
@lastUpdate  2026-04-28 22:41:00
@author      AI Agent
@version     1.0.0
"""

from typing import Optional
from shared.orchestration.state import AgentState


class OrderSecretaryState(AgentState):
    action_plan: str = "direct_answer"
    current_intent: Optional[str] = None
    intent_confidence: float = 0.0
    media_analysis: Optional[str] = None
