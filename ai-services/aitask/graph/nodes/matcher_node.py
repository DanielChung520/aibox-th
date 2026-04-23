"""
Matcher node for TopIntentRAG intent matching.

# Last Update: 2026-04-19 23:50:00
# Author: AI Agent
# Version: 1.2.0
"""

from aitask.graph.state import TopState
from aitask.top_intent_rag.router import match_intent as _match_intent_endpoint


async def matcher_node(state: TopState) -> dict[str, object]:
    """
    Match user message against orchestrator intents using TopIntentRAG.
    Determines action_plan based on matched intent.
    Supports multi-intent: emotion + task combinations.
    """
    messages = state["messages"]
    if not messages:
        return {
            "action_plan": "direct_answer",
            "matched_intent_data": None,
        }

    last_message = messages[-1]
    query = (
        last_message.content
        if isinstance(last_message.content, str)
        else str(last_message.content)
    )

    try:
        result = await _match_intent_endpoint(query=query, top_k=5)
        data = result.model_dump()
    except Exception:
        return {
            "action_plan": "unknown",
            "matched_intent_data": None,
        }

    best_match = data.get("best_match")
    if not best_match:
        return {
            "action_plan": "unknown",
            "matched_intent_data": None,
        }

    action_type = best_match.get("action_type", "direct_answer")
    action_plan = _map_action_type(action_type)

    return {
        "action_plan": action_plan,
        "matched_intent_data": data,
    }


def _map_action_type(action_type: str) -> str:
    """Map action_type from intent catalog to action_plan."""
    mapping = {
        "direct_answer": "direct_answer",
        "tool_call": "tool_call",
        "process_orchestration": "process_orchestration",
    }
    return mapping.get(action_type, "unknown")
