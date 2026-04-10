"""
@file        Data agent query node
@description Forwards natural language queries to Data Agent using Handoff v2.0 headers.
@lastUpdate  2026-04-11 03:12:30
@author      AI Agent
@version     1.0.0
"""

from __future__ import annotations

import json

import httpx
from langchain_core.messages import AIMessage, BaseMessage

from aitask.config import settings
from aitask.graph.state import TopState


def _message_text(message: BaseMessage) -> str:
    content = message.content
    return content if isinstance(content, str) else str(content)


def _headers(state: TopState) -> dict[str, str]:
    return {
        "X-Trace-Id": f"{state['session_id']}-{state['state_version']}",
        "X-Session-Id": state["session_id"],
        "X-Handoff-Schema-Version": "2.0",
    }


def _response_text(payload: dict[str, object]) -> str:
    if payload.get("code") == 0:
        explanation = payload.get("explanation") or payload.get("message")
        if explanation:
            return str(explanation)
        return json.dumps(payload, ensure_ascii=False, default=str)
    if payload.get("success") is True:
        execution_result = payload.get("execution_result")
        if isinstance(execution_result, dict):
            if isinstance(execution_result.get("rows"), list):
                return json.dumps(execution_result, ensure_ascii=False, default=str)
        if payload.get("generated_sql"):
            return json.dumps(payload, ensure_ascii=False, default=str)
    error_explanation = payload.get("error_explanation")
    if isinstance(error_explanation, dict) and error_explanation.get("explanation"):
        return str(error_explanation["explanation"])
    return str(payload.get("error") or payload.get("message") or "資料查詢失敗。")


async def da_query_node(state: TopState) -> dict[str, object]:
    query_text = _message_text(state["messages"][-1])
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{settings.services.data_agent_url.rstrip('/')}/query/query",
            json={"natural_language": query_text, "context": {"session_id": state["session_id"]}},
            headers=_headers(state),
        )
        response.raise_for_status()
        payload = response.json()

    if not isinstance(payload, dict):
        return {"messages": [AIMessage(content="資料代理回傳格式異常。")]}

    text = _response_text(payload)
    if payload.get("code") == 0 or payload.get("success") is True or payload.get("aql"):
        return {
            "messages": [AIMessage(content=text)],
            "state_version": state["state_version"] + 1,
        }
    return {"messages": [AIMessage(content=text)]}
