"""
Intent classifier stub.

# Last Update: 2026-04-11 02:57:52
# Author: AI Agent
# Version: 1.0.0
"""

from aitask.graph.state import TopState


async def classify_intent_node(state: TopState) -> dict[str, object]:
    return {
        "current_intent": "general_chat",
        "intent_confidence": 0.0,
        "intent_method": "rule",
    }
