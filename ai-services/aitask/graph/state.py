"""
Top-level LangGraph state.

# Last Update: 2026-04-14
# Author: AI Agent
# Version: 1.1.0
"""

from typing import Annotated, Literal, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages


class TopState(TypedDict):
    session_id: str
    user_id: str
    mode: Literal["chat", "task"]
    messages: Annotated[list[BaseMessage], add_messages]
    current_intent: Optional[str]
    intent_confidence: float
    intent_method: Literal["rule", "semantic", "llm"]
    # Action plan determined by TopIntentRAG
    action_plan: Literal["direct_answer", "tool_call", "process_orchestration", "unknown"]
    # Full matched intent data from TopIntentRAG
    matched_intent_data: Optional[dict[str, object]]
    entities: dict[str, str]
    coreference_resolved: bool
    context_entities: dict[str, str]
    active_bpa: Optional[str]
    bpa_workflow_id: Optional[str]
    bpa_state: Literal[
        "idle", "executing", "waiting_for_user", "completed", "failed"
    ]
    tool_results: list[dict[str, object]]
    pending_tool_calls: list[dict[str, object]]
    short_term_memory: list[dict[str, object]]
    long_term_memory: list[dict[str, object]]
    memory_turn_count: int
    protocol_version: str
    state_version: int
    checkpoint_version: int
