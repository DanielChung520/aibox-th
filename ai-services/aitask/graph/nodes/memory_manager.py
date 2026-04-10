"""
Memory manager node.

# Last Update: 2026-04-11 02:57:52
# Author: AI Agent
# Version: 1.0.0
"""

from langchain_core.messages import BaseMessage

from aitask.graph.state import TopState

MAX_MESSAGES = 20


def _message_text(message: BaseMessage) -> str:
    content = message.content
    return content if isinstance(content, str) else str(content)


def _message_role(message: BaseMessage) -> str:
    message_type = getattr(message, "type", "human")
    if message_type == "human":
        return "user"
    if message_type == "ai":
        return "assistant"
    return "system"


def _memory_entry(message: BaseMessage) -> dict[str, object]:
    return {"role": _message_role(message), "content": _message_text(message)}


async def memory_manager_node(state: TopState) -> dict[str, object]:
    messages = state["messages"]
    trimmed_messages = messages[-MAX_MESSAGES:] if len(messages) > MAX_MESSAGES else messages
    short_term_memory = [_memory_entry(message) for message in trimmed_messages]
    return {
        "messages": trimmed_messages,
        "short_term_memory": short_term_memory,
        "memory_turn_count": state["memory_turn_count"] + 1,
    }
