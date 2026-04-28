"""
@file        Ragic Agent — Graph Builder
@description 使用 AgentGraphBuilder 建構 LangGraph
@lastUpdate  2026-04-27 19:30:00
@author      AI Agent
@version     1.0.0
"""

from langgraph.graph import END

from shared.orchestration.builder import AgentGraphBuilder

from bpa.ragic_agent.graph.nodes.intent_classifier import classify_intent
from bpa.ragic_agent.graph.nodes.ragic_handler import ragic_handler_node


def build_ragic_graph():
    builder = AgentGraphBuilder()

    builder.add_node("classify_intent", classify_intent)
    builder.add_node("ragic_handler", ragic_handler_node)

    builder.set_entry("classify_intent")
    builder.add_edge("classify_intent", "ragic_handler")
    builder.add_edge("ragic_handler", END)

    return builder.build()
