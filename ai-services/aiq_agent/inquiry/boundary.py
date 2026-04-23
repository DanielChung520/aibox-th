"""
@file        Inquiry Layer Boundary Rules
@description 以規則評估意圖邊界充分性與升級條件。
@lastUpdate  2026-04-18 19:34:34
@author      Daniel Chung
@version     1.0.0
"""

from __future__ import annotations

from aiq_agent.inquiry.models import BoundaryStatus, BoundaryStatusEnum, ExecutionPath, Hypothesis
from aiq_agent.perception.models import WorkingContext


def evaluate_boundary(
    hypotheses: list[Hypothesis],
    working_context: WorkingContext,
) -> BoundaryStatus:
    """Evaluate current hypothesis sufficiency using rule-based heuristics."""
    if not hypotheses:
        return BoundaryStatus(
            status=BoundaryStatusEnum.INSUFFICIENT,
            missing_dimensions=["intent_signal", "query_goal"],
            suggested_questions=["你想完成什麼任務？", "目前最需要哪一類協助？"],
        )

    ranked = sorted(hypotheses, key=lambda item: item.confidence, reverse=True)
    top_hypothesis = ranked[0]
    evidence_sources = {evidence.source for evidence in top_hypothesis.evidence_chain}

    if len(ranked) >= 2:
        second_hypothesis = ranked[1]
        confidence_gap = top_hypothesis.confidence - second_hypothesis.confidence
        if (
            top_hypothesis.execution_path != second_hypothesis.execution_path
            and confidence_gap < 0.15
        ):
            return BoundaryStatus(
                status=BoundaryStatusEnum.INSUFFICIENT,
                missing_dimensions=["execution_route_disambiguation"],
                suggested_questions=[
                    "你希望我提供操作指引、資料查詢，還是直接給出答案？"
                ],
            )

    if top_hypothesis.confidence >= 0.8 and len(evidence_sources) >= 2:
        return BoundaryStatus(status=BoundaryStatusEnum.SUFFICIENT)

    if top_hypothesis.confidence < 0.3:
        return BoundaryStatus(
            status=BoundaryStatusEnum.OUT_OF_SCOPE,
            missing_dimensions=["domain_fit"],
            suggested_questions=[
                "這個需求是否與目前頁面或系統中的資料、功能有關？",
                "你可以改成描述想查詢的資料、想操作的功能或想取得的知識嗎？",
            ],
        )

    if len(evidence_sources) < 2:
        missing_dimensions = ["multi_source_evidence"]
        if not working_context.active_anchors:
            missing_dimensions.append("active_anchor")
        if top_hypothesis.execution_path == ExecutionPath.ROUTE_TO_DATA:
            missing_dimensions.append("data_scope")
        return BoundaryStatus(
            status=BoundaryStatusEnum.INSUFFICIENT,
            missing_dimensions=missing_dimensions,
            suggested_questions=[
                "請補充你要處理的資料範圍、頁面位置或目標對象。"
            ],
        )

    return BoundaryStatus(
        status=BoundaryStatusEnum.INSUFFICIENT,
        missing_dimensions=["decision_gap"],
        suggested_questions=["請再補充一個你最在意的結果或限制條件。"],
    )


def check_escalation(
    hypotheses: list[Hypothesis],
    boundary: BoundaryStatus,
) -> str | None:
    """Determine whether human-in-the-loop escalation is required."""
    ranked = sorted(hypotheses, key=lambda item: item.confidence, reverse=True)

    if len(ranked) >= 2 and ranked[0].confidence - ranked[1].confidence < 0.05:
        return "Top inquiry hypotheses are nearly tied and require human review."

    if (
        boundary.status == BoundaryStatusEnum.OUT_OF_SCOPE
        and not boundary.suggested_questions
    ):
        return "Inquiry is out of scope without viable clarification path."

    if any(hypothesis.execution_path == ExecutionPath.TOOL_CALL for hypothesis in ranked):
        return "Inquiry may trigger side-effecting tool execution and requires approval."

    return None
