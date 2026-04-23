"""
@file        Agent state definitions
@description Minimal shared state that all agents extend. TypedDict with LangGraph add_messages.
@lastUpdate  2026-04-21 10:00:00
@author      Daniel Chung
@version     1.0.0
"""

from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages


class AgentState(TypedDict):
    session_id: str
    user_id: str
    messages: Annotated[list[BaseMessage], add_messages]
    state_version: int
    tool_results: list[dict[str, Any]]
    pending_tool_calls: list[dict[str, Any]]
    extra: dict[str, Any]


class AgentRunResult(TypedDict):
    session_id: str
    response: str
    messages: list[BaseMessage]
    tool_results: list[dict[str, Any]]
    state_version: int
    trace_id: str
    success: bool
    error: str | None