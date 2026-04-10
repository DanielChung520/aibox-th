"""
@file        BPA orchestrator node
@description Stub BPA orchestrator node for future workflow execution support.
@lastUpdate  2026-04-11 03:12:30
@author      AI Agent
@version     1.0.0
"""

from langchain_core.messages import AIMessage

from aitask.graph.state import TopState


async def bpa_orchestrator_node(state: TopState) -> dict[str, object]:
    del state
    return {
        "messages": [AIMessage(content="BPA 流程功能開發中，目前暫不支援。")],
        "bpa_state": "idle",
    }
