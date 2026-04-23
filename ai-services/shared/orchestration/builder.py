"""
@file        Agent graph builder
@description Helper to build LangGraph StateGraph with standard routing.
@lastUpdate  2026-04-21 10:00:00
@author      Daniel Chung
@version     1.0.0
"""

from typing import Callable

from langgraph.graph import START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from shared.orchestration.state import AgentState


class AgentGraphBuilder:
    def __init__(self) -> None:
        self._graph = StateGraph(AgentState)
        self._nodes: dict[str, Callable] = {}
        self._entry: str | None = None
        self._conditional: dict[str, tuple[Callable, dict[str, str]]] = {}

    def add_node(self, name: str, fn: Callable) -> None:
        self._nodes[name] = fn
        self._graph.add_node(name, fn)

    def set_entry(self, name: str) -> None:
        self._entry = name

    def add_edge(self, from_node: str, to_node: str) -> None:
        self._graph.add_edge(from_node, to_node)

    def add_conditional_edges(
        self,
        from_node: str,
        router: Callable,
        mapping: dict[str, str],
    ) -> None:
        self._conditional[from_node] = (router, mapping)
        self._graph.add_conditional_edges(from_node, router, mapping)  # type: ignore[arg-type]

    def build(self) -> CompiledStateGraph:
        if self._entry is None:
            raise ValueError("Entry node not set. Call set_entry() first.")
        self._graph.add_edge(START, self._entry)
        for from_node, (router, mapping) in self._conditional.items():
            self._graph.add_conditional_edges(from_node, router, mapping)  # type: ignore[arg-type]
        return self._graph.compile()  # type: ignore[return-value]