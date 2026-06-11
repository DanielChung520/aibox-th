"""
@file        Knowledge agent search node
@description Sends user queries to Knowledge Agent and returns the RAG response.
@lastUpdate  2026-04-11 03:12:30
@author      AI Agent
@version     1.0.0
"""

from __future__ import annotations

import httpx
from langchain_core.messages import AIMessage, BaseMessage

from aitask.config import settings
from aitask.graph.state import TopState


def _message_text(message: BaseMessage) -> str:
    content = message.content
    return content if isinstance(content, str) else str(content)


async def ka_search_node(state: TopState) -> dict[str, object]:
    query_text = _message_text(state["messages"][-1])
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{settings.services.knowledge_agent_url.rstrip('/')}/query",
            json={"query": query_text, "limit": 5},
            headers={
                "X-Trace-Id": f"{state['session_id']}-{state['state_version']}",
                "X-Session-Id": state["session_id"],
                "X-Handoff-Schema-Version": "2.0",
            },
        )
        if response.status_code == 404:
            response = await client.post(
                f"{settings.services.knowledge_agent_url.rstrip('/')}/search",
                json={"query": query_text, "limit": 5},
            )
        response.raise_for_status()
        payload = response.json()

    rag_response = payload.get("rag_response") if isinstance(payload, dict) else None
    if not rag_response and isinstance(payload, dict):
        rag_response = payload.get("answer") or payload.get("message") or payload.get("context")
    return {
        "messages": [AIMessage(content=str(rag_response or "知識代理未回傳結果。"))],
        "state_version": state["state_version"] + 1,
    }
