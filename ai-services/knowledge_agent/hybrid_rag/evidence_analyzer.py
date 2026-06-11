"""
HybridRAG v2 Evidence Analyzer — Contradiction Detection + Gap Analysis.

依據 HybridRAG-細部規格書-v2.md Section 9 Evidence Assembly Contract。

職責：
- 候選轉 EvidenceUnit
- 檢測 supports / contradicts 標記
- 缺口檢測
- 充足性評估

@lastUpdate: 2026-04-18 00:43:35
@author: Daniel Chung
@version: 2.0.0
"""

from __future__ import annotations

from typing import Any

from knowledge_agent.hybrid_rag.models.evidence import (
    EvidenceSet,
    EvidenceUnit,
    NextStep,
    Sufficiency,
)


class EvidenceAnalyzer:
    def analyze(
        self,
        evidence_units: list[EvidenceUnit],
        hypothesis: Any,
        inquiry_plan: Any | None = None,
    ) -> tuple[EvidenceSet, list[str]]:
        """分析 EvidenceUnit 清單，產出 EvidenceSet 與缺口列表。

        Args:
            evidence_units: 已收集的 evidence unit 清單。
            hypothesis: 目標 hypothesis。
            inquiry_plan: 可選的 inquiry plan，用於缺口檢測。

        Returns:
            Tuple of (EvidenceSet, list of gap descriptions).
        """
        required_types = set(hypothesis.required_evidence_types or [])
        hypothesis_id = hypothesis.hypothesis_id or ""

        supports_ids: list[str] = []
        contradicts_ids: list[str] = []
        gaps: list[str] = []

        for eu in evidence_units:
            if eu.supports and hypothesis_id in eu.supports:
                supports_ids.append(eu.evidence_id or "")
            if eu.contradicts and hypothesis_id in eu.contradicts:
                contradicts_ids.append(eu.evidence_id or "")

        if required_types:
            collected_types = self._infer_collected_types(evidence_units)
            missing = required_types - collected_types
            for mt in missing:
                gaps.append(f"缺少指定證據類型：{mt}")

        sufficiency = self._evaluate_sufficiency(
            len(supports_ids),
            len(contradicts_ids),
            len(gaps),
        )

        next_step = self._resolve_next_step(
            sufficiency,
            contradicts_ids,
            gaps,
        )

        evidence_set = EvidenceSet(
            hypothesis_id=hypothesis_id,
            evidences=supports_ids,
            contradictions=contradicts_ids,
            gaps=gaps,
            sufficiency=sufficiency,
            next_step=next_step,
        )

        return evidence_set, gaps

    def _infer_collected_types(self, evidence_units: list[EvidenceUnit]) -> set[str]:
        types: set[str] = set()
        for eu in evidence_units:
            if eu.source_type.value == "vector":
                types.add("source_chunk")
            elif eu.source_type.value == "graph":
                types.add("graph_relation")
            elif eu.source_type.value == "raw":
                types.add("table_context")
        return types

    def _evaluate_sufficiency(
        self,
        num_supports: int,
        num_contradicts: int,
        num_gaps: int,
    ) -> Sufficiency:
        if num_contradicts > 0:
            return Sufficiency.CONFLICTED
        if num_supports > 0 and num_gaps == 0:
            return Sufficiency.SUFFICIENT
        return Sufficiency.INSUFFICIENT

    def _resolve_next_step(
        self,
        sufficiency: Sufficiency,
        contradicts: list[str],
        gaps: list[str],
    ) -> NextStep:
        if sufficiency == Sufficiency.CONFLICTED:
            return NextStep.HANDOFF_TO_HUMAN
        if sufficiency == Sufficiency.SUFFICIENT:
            return NextStep.STOP
        if gaps:
            return NextStep.EXPAND_GRAPH
        return NextStep.STOP


_evidence_analyzer: EvidenceAnalyzer | None = None


def get_evidence_analyzer() -> EvidenceAnalyzer:
    global _evidence_analyzer
    if _evidence_analyzer is None:
        _evidence_analyzer = EvidenceAnalyzer()
    return _evidence_analyzer
