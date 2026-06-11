"""
HybridRAG v2 Inquiry Decomposer — Hypothesis → InquiryPlan 轉換.

依據 HybridRAG-細部規格書-v2.md Section 8 Inquiry Decomposition Contract。

職責：
- 分析 Hypothesis 的 statement 和 candidate_anchors
- 產生 sub_questions（分解後的子問題）
- 決定 allowed_channels
- 分配 cost_budget
- 設定 stop_conditions

也處理無 Hypothesis 的查詢（隱性 Hypothesis）。

@lastUpdate: 2026-04-18 00:43:35
@author: Daniel Chung
@version: 2.0.0
"""

from __future__ import annotations

import uuid
from typing import Any

from knowledge_agent.hybrid_rag.models.inquiry import (
    Boundary,
    Hypothesis,
    InquiryPlan,
    InquiryStrategy,
)


class InquiryDecomposer:
    def decompose(
        self,
        hypothesis: Hypothesis,
        boundary: Boundary,
        query: str = "",
    ) -> InquiryPlan:
        """將 Hypothesis 轉為 InquiryPlan。

        Args:
            hypothesis: The hypothesis to decompose.
            boundary: Boundary for cost budgeting.
            query: Original query string.

        Returns:
            InquiryPlan with sub_questions, allowed_channels, and stop conditions.
        """
        anchors = hypothesis.candidate_anchors or []
        required_types = hypothesis.required_evidence_types or []

        sub_questions = self._generate_sub_questions(hypothesis.statement, anchors)
        allowed_channels = self._resolve_channels(required_types)
        stop_when = self._resolve_stop_conditions(hypothesis)

        return InquiryPlan(
            plan_id=f"ip_{uuid.uuid4().hex[:12]}",
            strategy=self._resolve_strategy(hypothesis, required_types),
            sub_questions=sub_questions,
            allowed_channels=allowed_channels,
            stop_when=stop_when,
        )

    def _generate_sub_questions(self, statement: str, anchors: list[str]) -> list[str]:
        sub_questions: list[str] = []
        if anchors:
            sub_questions.append(f"哪個 anchor 最可能是當前查詢中心？候選：{', '.join(anchors)}")
        sub_questions.append("有哪些結構化關係可支持這個假設？")
        sub_questions.append("有哪些語義片段能補足上下文？")
        if "graph_relation" in statement or "關係" in statement:
            sub_questions.append("實體之間的關係路徑是什麼？")
        if "source_chunk" in statement or "原始" in statement:
            sub_questions.append("原始文件來源是否可驗證？")
        return sub_questions

    def _resolve_channels(self, required_types: list[str]) -> list[str]:
        channel_map = {
            "graph_relation": ["graph", "vector"],
            "source_chunk": ["vector", "raw"],
            "table_context": ["vector"],
            "entityAnchor": ["graph"],
        }
        channels: list[str] = ["vector", "graph"]
        for rt in required_types:
            if rt in channel_map:
                for ch in channel_map[rt]:
                    if ch not in channels:
                        channels.append(ch)
        return channels

    def _resolve_strategy(self, hypothesis: Hypothesis, required_types: list[str]) -> InquiryStrategy:
        if "graph_relation" in required_types or hypothesis.candidate_anchors:
            return InquiryStrategy.GRAPH_FIRST
        if "source_chunk" in required_types:
            return InquiryStrategy.VECTOR_ONLY
        return InquiryStrategy.HYBRID

    def _resolve_stop_conditions(self, hypothesis: Hypothesis) -> list[str]:
        conditions = ["evidence_sufficient", "boundary_unclear", "budget_exhausted"]
        if hypothesis.falsifiable_by:
            conditions.append("contradictory_unresolved")
        return conditions

    def create_implicit_hypothesis(
        self,
        query: str,
        boundary: Boundary,
        context_signals: Any | None = None,
    ) -> Hypothesis:
        """從純 query（無 Hypothesis）自動生成隱性 Hypothesis。

        Args:
            query: The natural language query.
            boundary: Boundary for scope.
            context_signals: Optional context signals for anchor inference.

        Returns:
            Hypothesis with auto-generated id and inferred attributes.
        """
        anchors: list[str] = []
        required_types: list[str] = ["source_chunk"]

        if context_signals and hasattr(context_signals, "candidate_anchors"):
            anchors = context_signals.candidate_anchors or []
        if context_signals and hasattr(context_signals, "active_table"):
            at = context_signals.active_table
            if at:
                anchors.append(at)
                required_types.append("table_context")

        if any(kw in query for kw in ["關係", "連接", "哪個", "誰"]):
            required_types.append("graph_relation")

        return Hypothesis(
            hypothesis_id=f"ih_{uuid.uuid4().hex[:12]}",
            statement=query,
            candidate_anchors=anchors,
            required_evidence_types=required_types,
            falsifiable_by=["找不到相關資訊", "查詢超出邊界"],
        )


_inquiry_decomposer: InquiryDecomposer | None = None


def get_inquiry_decomposer() -> InquiryDecomposer:
    global _inquiry_decomposer
    if _inquiry_decomposer is None:
        _inquiry_decomposer = InquiryDecomposer()
    return _inquiry_decomposer
