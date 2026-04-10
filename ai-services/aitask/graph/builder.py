"""
LangGraph builder for AITask.

# Last Update: 2026-04-11 02:57:52
# Author: AI Agent
# Version: 1.0.0
"""

from typing import cast

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Checkpointer

from aitask.graph.nodes import (
    bpa_orchestrator_node,
    chat_responder_node,
    classify_intent_node,
    da_query_node,
    ka_search_node,
    memory_manager_node,
    resolve_coreference_node,
    tool_executor_node,
)
from aitask.graph.state import TopState


def route_by_intent(state: TopState) -> str:
    intent = state.get("current_intent") or "general_chat"
    valid_intents = {"general_chat", "data_query", "knowledge", "tool_use", "bpa_task"}
    return intent if intent in valid_intents else "general_chat"


def build_graph(
    checkpointer: Checkpointer | None,
) -> CompiledStateGraph[TopState, None, TopState, TopState]:
    graph = StateGraph(TopState)
    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("resolve_coreference", resolve_coreference_node)
    graph.add_node("chat_responder", chat_responder_node)
    graph.add_node("tool_executor", tool_executor_node)
    graph.add_node("bpa_orchestrator", bpa_orchestrator_node)
    graph.add_node("da_query", da_query_node)
    graph.add_node("ka_search", ka_search_node)
    graph.add_node("memory_manager", memory_manager_node)
    graph.add_edge(START, "classify_intent")
    graph.add_edge("classify_intent", "resolve_coreference")
    graph.add_conditional_edges(
        "resolve_coreference",
        route_by_intent,
        {
            "general_chat": "chat_responder",
            "data_query": "da_query",
            "knowledge": "ka_search",
            "tool_use": "tool_executor",
            "bpa_task": "bpa_orchestrator",
        },
    )
    graph.add_edge("chat_responder", "memory_manager")
    graph.add_edge("da_query", "memory_manager")
    graph.add_edge("ka_search", "memory_manager")
    graph.add_edge("tool_executor", "memory_manager")
    graph.add_edge("bpa_orchestrator", "memory_manager")
    graph.add_edge("memory_manager", END)
    return cast(
        CompiledStateGraph[TopState, None, TopState, TopState],
        graph.compile(checkpointer=checkpointer),
    )
