"""
@file        Orchestration engine
@description Main entry point for running an agent graph with tool loop support.
@lastUpdate  2026-04-21 10:00:00
@author      Daniel Chung
@version     1.0.0
"""

import uuid
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from shared.orchestration.state import AgentRunResult, AgentState
from shared.orchestration.nodes.tool_executor import tool_executor_node


class OrchestrationEngine:
    def __init__(
        self,
        graph: Any,
        max_tool_loops: int = 3,
    ) -> None:
        self._graph = graph
        self._max_tool_loops = max_tool_loops

    async def run(
        self,
        session_id: str,
        user_id: str,
        user_message: str,
        tools: list[dict[str, Any]] | None = None,
        seed_messages: list[BaseMessage] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> AgentRunResult:
        trace_id = f"{session_id}-{uuid.uuid4().hex[:8]}"
        all_messages: list[BaseMessage] = []
        if seed_messages:
            all_messages.extend(seed_messages)
        all_messages.append(HumanMessage(content=user_message))
        state: AgentState = {
            "session_id": session_id,
            "user_id": user_id,
            "messages": all_messages,
            "state_version": 0,
            "tool_results": [],
            "pending_tool_calls": [],
            "extra": extra or {},
        }

        try:
            config = {"configurable": {"thread_id": session_id}}

            if not tools:
                result = await self._graph.ainvoke(state, config)
                return self._build_result(result, session_id, trace_id, True, None)

            for loop_idx in range(self._max_tool_loops):
                result = await self._graph.ainvoke(state, config)
                state = result

                last_message = result["messages"][-1] if result.get("messages") else None
                if not isinstance(last_message, AIMessage):
                    break

                tool_calls = getattr(last_message, "tool_calls", None) or []
                if not tool_calls:
                    break

                executor_result = await tool_executor_node(state)
                tool_msgs = executor_result.get("messages", [])
                state["messages"] = state["messages"] + tool_msgs
                state["state_version"] = executor_result.get("state_version", state["state_version"] + 1)

            final_message = state["messages"][-1] if state["messages"] else None
            raw_content = getattr(final_message, "content", "") if final_message else ""
            response_text = raw_content if isinstance(raw_content, str) else ""

            return AgentRunResult(
                session_id=session_id,
                response=response_text,
                messages=state["messages"],
                tool_results=state["tool_results"],
                state_version=state["state_version"],
                trace_id=trace_id,
                success=True,
                error=None,
            )

        except Exception as exc:
            return AgentRunResult(
                session_id=session_id,
                response="",
                messages=state["messages"],
                tool_results=state["tool_results"],
                state_version=state["state_version"],
                trace_id=trace_id,
                success=False,
                error=str(exc),
            )

    def _build_result(
        self,
        result: AgentState,
        session_id: str,
        trace_id: str,
        success: bool,
        error: str | None,
    ) -> AgentRunResult:
        last_message = result["messages"][-1] if result.get("messages") else None
        raw_content = getattr(last_message, "content", "") if last_message else ""
        response_text = raw_content if isinstance(raw_content, str) else ""
        return AgentRunResult(
            session_id=session_id,
            response=response_text,
            messages=result["messages"],
            tool_results=result.get("tool_results", []),
            state_version=result.get("state_version", 0),
            trace_id=trace_id,
            success=success,
            error=error,
        )