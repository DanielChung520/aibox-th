"""
@file        Router node
@description Routes to the appropriate next node based on action_plan in state.
@lastUpdate  2026-04-21 10:00:00
@author      Daniel Chung
@version     1.0.0
"""


from shared.orchestration.state import AgentState


def router_node(state: AgentState) -> str:
    action_plan = state.get("action_plan", "direct_answer")
    return str(action_plan)


def route_by_action(state: AgentState) -> str:
    return router_node(state)