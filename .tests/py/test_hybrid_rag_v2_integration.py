"""
HybridRAG v2 Integration Tests

Tests against real ArangoDB + Qdrant + Ollama services.
Requires running ArangoDB (localhost:8529), Qdrant (localhost:6333), Ollama (localhost:11434).

Run with: .venv/bin/python .tests/py/test_hybrid_rag_v2_integration.py

@lastUpdate: 2026-04-18 00:43:35
@author: Daniel Chung
@version: 2.0.0
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../ai-services"))

from knowledge_agent.hybrid_rag.boundary_checker import BoundaryChecker
from knowledge_agent.hybrid_rag.models.inquiry import (
    Boundary,
    ContextSignals,
    EvidenceSearchRequest,
    Hypothesis,
    InquiryPlan,
    InquiryStrategy,
)
from knowledge_agent.hybrid_rag.models.evidence import (
    EvidenceProvenance,
    EvidenceUnit,
    SourceType,
)


def test_boundary_checker_real_arango():
    """Test boundary_checker against real ArangoDB knowledge_roots."""
    checker = BoundaryChecker()
    boundary = Boundary(root_id="kb_1776390288341")
    result = checker.check(boundary)
    assert result.status in ("within_boundary", "out_of_boundary")
    assert isinstance(result.passed_checks, list)
    assert isinstance(result.failed_checks, list)
    print(f"[PASS] boundary_checker real ArangoDB: {result.status}")


def test_boundary_checker_nonexistent_root():
    """Test with non-existent knowledge base."""
    checker = BoundaryChecker()
    boundary = Boundary(root_id="kb_nonexistent_12345")
    result = checker.check(boundary)
    assert result.status == "out_of_boundary"
    print(f"[PASS] boundary_checker nonexistent root: correctly rejected")


def test_evidence_analyzer_conflicted():
    """Test evidence analyzer with conflicting evidence."""
    from knowledge_agent.hybrid_rag.evidence_analyzer import EvidenceAnalyzer
    analyzer = EvidenceAnalyzer()
    eu_support = EvidenceUnit(
        evidence_id="ev_support",
        source_type=SourceType.VECTOR,
        content="this batch was supplied by supplier A",
        supports=["ih_test"],
    )
    eu_contradict = EvidenceUnit(
        evidence_id="ev_contradict",
        source_type=SourceType.GRAPH,
        content="this batch was supplied by supplier B",
        contradicts=["ih_test"],
    )
    hyp = Hypothesis(hypothesis_id="ih_test")
    evidence_set, gaps = analyzer.analyze([eu_support, eu_contradict], hyp)
    assert "ev_support" in evidence_set.evidences
    assert "ev_contradict" in evidence_set.contradictions
    assert evidence_set.sufficiency.value == "conflicted"
    print(f"[PASS] evidence_analyzer conflicted: next_step={evidence_set.next_step.value}")


def test_evidence_analyzer_sufficient():
    """Test evidence analyzer with sufficient support."""
    from knowledge_agent.hybrid_rag.evidence_analyzer import EvidenceAnalyzer
    analyzer = EvidenceAnalyzer()
    eu = EvidenceUnit(
        evidence_id="ev_1",
        source_type=SourceType.VECTOR,
        content="quality check passed",
        supports=["ih_qa"],
    )
    hyp = Hypothesis(
        hypothesis_id="ih_qa",
        required_evidence_types=["source_chunk"],
    )
    evidence_set, gaps = analyzer.analyze([eu], hyp)
    assert evidence_set.sufficiency.value == "sufficient"
    assert evidence_set.next_step.value == "stop"
    print(f"[PASS] evidence_analyzer sufficient: correctly identified")


def test_inquiry_decomposer_real():
    """Test inquiry decomposer with realistic hypothesis."""
    from knowledge_agent.hybrid_rag.inquiry_decomposer import InquiryDecomposer
    decomposer = InquiryDecomposer()
    boundary = Boundary(root_id="kb_1776390288341", max_hops=2, max_top_k=10)
    hyp = Hypothesis(
        hypothesis_id="ih_batch_inquiry",
        statement="查詢退貨批次的供應商與品質檢驗結果關聯",
        candidate_anchors=["batch_id", "supplier_id", "qc_result_id"],
        required_evidence_types=["graph_relation", "source_chunk"],
        falsifiable_by=["找不到對應批號", "跨越知識邊界"],
    )
    plan = decomposer.decompose(hyp, boundary, "退貨批次的供應商是誰？")
    assert plan.strategy in (InquiryStrategy.HYBRID, InquiryStrategy.GRAPH_FIRST)
    assert "graph" in plan.allowed_channels
    assert len(plan.sub_questions) >= 2
    print(f"[PASS] inquiry_decomposer: strategy={plan.strategy.value}, channels={plan.allowed_channels}")


def test_inquiry_decomposer_implicit():
    """Test implicit hypothesis creation from query."""
    from knowledge_agent.hybrid_rag.inquiry_decomposer import InquiryDecomposer
    decomposer = InquiryDecomposer()
    boundary = Boundary(root_id="kb_1776390288341")
    hyp = decomposer.create_implicit_hypothesis(
        "如何建立供應商主檔？",
        boundary,
    )
    assert hyp.hypothesis_id.startswith("ih_")
    assert hyp.statement == "如何建立供應商主檔？"
    assert "source_chunk" in hyp.required_evidence_types
    print(f"[PASS] implicit hypothesis: id={hyp.hypothesis_id}")


def test_state_machine_stopped():
    """Test state machine compute_next_state for stopped."""
    from knowledge_agent.hybrid_rag.state_machine import HybridRAGState, compute_next_state
    state = compute_next_state("out_of_boundary", None, None)
    assert state == HybridRAGState.STOPPED
    state2 = compute_next_state(None, "sufficient", None)
    assert state2 == HybridRAGState.STOPPED
    print(f"[PASS] state machine stopped states: {state.value}, {state2.value}")


def test_state_machine_clarify():
    """Test state machine for clarify_required."""
    from knowledge_agent.hybrid_rag.state_machine import HybridRAGState, compute_next_state
    state = compute_next_state("boundary_unclear", None, None)
    assert state == HybridRAGState.CLARIFY_REQUIRED
    state2 = compute_next_state(None, "conflicted", None)
    assert state2 == HybridRAGState.CLARIFY_REQUIRED
    print(f"[PASS] state machine clarify states: {state.value}, {state2.value}")


def test_state_machine_handoff():
    """Test state machine for handoff_required."""
    from knowledge_agent.hybrid_rag.state_machine import HybridRAGState, compute_next_state
    state = compute_next_state(None, None, "handoff_to_human")
    assert state == HybridRAGState.HANDOFF_REQUIRED
    print(f"[PASS] state machine handoff: {state.value}")


def test_state_machine_active():
    """Test state machine for active states."""
    from knowledge_agent.hybrid_rag.state_machine import HybridRAGState, compute_next_state
    state = compute_next_state("within_boundary", "insufficient", "expand_graph")
    assert state == HybridRAGState.RETRIEVING
    state2 = compute_next_state(None, "insufficient", None, has_hypothesis=False)
    assert state2 == HybridRAGState.PLANNING
    print(f"[PASS] state machine active: {state.value}, {state2.value}")


def test_evidence_unit_autogeneration():
    """Test EvidenceUnit auto-generates IDs."""
    eu = EvidenceUnit(content="test content")
    assert eu.evidence_id is not None
    assert eu.evidence_id.startswith("ev_")
    print(f"[PASS] EvidenceUnit auto-id: {eu.evidence_id}")


def test_boundary_model_defaults():
    """Test Boundary model defaults."""
    b = Boundary(root_id="kb_test")
    assert b.max_hops == 2
    assert b.max_top_k == 10
    assert b.time_budget_ms == 2000
    print(f"[PASS] Boundary defaults: max_hops={b.max_hops}, max_top_k={b.max_top_k}")


def test_hypothesis_autogeneration():
    """Test Hypothesis auto-generates ID."""
    h = Hypothesis(statement="test")
    assert h.hypothesis_id is not None
    assert h.hypothesis_id.startswith("ih_")
    print(f"[PASS] Hypothesis auto-id: {h.hypothesis_id}")


def test_inquiry_plan_defaults():
    """Test InquiryPlan defaults."""
    ip = InquiryPlan()
    assert ip.strategy == InquiryStrategy.HYBRID
    assert "vector" in ip.allowed_channels
    assert "graph" in ip.allowed_channels
    assert "evidence_sufficient" in ip.stop_when
    print(f"[PASS] InquiryPlan defaults: strategy={ip.strategy.value}")


def test_context_signals():
    """Test ContextSignals."""
    cs = ContextSignals(
        active_page="SchemaPage",
        active_table="產品主檔",
        candidate_anchors=["item_id", "supplier_id"],
    )
    d = cs.to_dict()
    assert d["active_page"] == "SchemaPage"
    assert d["active_table"] == "產品主檔"
    assert "item_id" in d["candidate_anchors"]
    print(f"[PASS] ContextSignals: page={d['active_page']}")


if __name__ == "__main__":
    print("=== HybridRAG v2 Integration Tests ===\n")
    test_boundary_checker_real_arango()
    test_boundary_checker_nonexistent_root()
    test_evidence_analyzer_conflicted()
    test_evidence_analyzer_sufficient()
    test_inquiry_decomposer_real()
    test_inquiry_decomposer_implicit()
    test_state_machine_stopped()
    test_state_machine_clarify()
    test_state_machine_handoff()
    test_state_machine_active()
    test_evidence_unit_autogeneration()
    test_boundary_model_defaults()
    test_hypothesis_autogeneration()
    test_inquiry_plan_defaults()
    test_context_signals()
    print("\n=== All Integration Tests Passed ===")
