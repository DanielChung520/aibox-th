"""
HybridRAG v2 Models Unit Tests

Tests for EvidenceUnit, EvidenceSet, AuditRecord, Boundary, Hypothesis,
InquiryPlan, ContextSignals, and EvidenceSearchRequest.

@lastUpdate: 2026-04-18 00:43:35
@author: Daniel Chung
@version: 2.0.0
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../ai-services"))

from knowledge_agent.hybrid_rag.models.evidence import (
    AuditRecord,
    BoundaryStatus,
    EvidenceProvenance,
    EvidenceSearchResponse,
    EvidenceSet,
    EvidenceUnit,
    NextStep,
    SourceType,
    Sufficiency,
)
from knowledge_agent.hybrid_rag.models.inquiry import (
    Boundary,
    ContextSignals,
    EvidenceSearchRequest,
    Hypothesis,
    InquiryPlan,
    InquiryStrategy,
)


def test_evidence_unit_auto_id():
    eu = EvidenceUnit(content="test content")
    assert eu.evidence_id is not None
    assert eu.evidence_id.startswith("ev_")
    assert eu.source_type == SourceType.VECTOR
    assert eu.normalized_score == 0.0
    assert eu.supports == []
    assert eu.contradicts == []


def test_evidence_unit_to_dict():
    eu = EvidenceUnit(
        evidence_id="ev_test123",
        source_type=SourceType.GRAPH,
        root_id="kb_123",
        file_id="file_456",
        chunk_index=3,
        content="some evidence",
        normalized_score=0.85,
        extraction_confidence=0.9,
        supports=["ih_abc"],
        contradicts=["ih_xyz"],
        provenance=EvidenceProvenance(lifecycle_status="active"),
    )
    d = eu.to_dict()
    assert d["evidence_id"] == "ev_test123"
    assert d["source_type"] == "graph"
    assert d["root_id"] == "kb_123"
    assert d["normalized_score"] == 0.85
    assert d["supports"] == ["ih_abc"]
    assert d["contradicts"] == ["ih_xyz"]


def test_evidence_set_defaults():
    es = EvidenceSet(hypothesis_id="ih_test")
    assert es.hypothesis_id == "ih_test"
    assert es.boundary_status == BoundaryStatus.WITHIN_BOUNDARY
    assert es.sufficiency == Sufficiency.INSUFFICIENT
    assert es.evidences == []
    assert es.contradictions == []
    assert es.gaps == []
    assert es.next_step == NextStep.STOP


def test_evidence_set_to_dict():
    es = EvidenceSet(
        hypothesis_id="ih_test",
        boundary_status=BoundaryStatus.OUT_OF_BOUNDARY,
        sufficiency=Sufficiency.CONFLICTED,
        evidences=["ev_1", "ev_2"],
        contradictions=["ev_3"],
        gaps=["missing_source_doc"],
        next_step=NextStep.HANDOFF_TO_HUMAN,
    )
    d = es.to_dict()
    assert d["hypothesis_id"] == "ih_test"
    assert d["boundary_status"] == "out_of_boundary"
    assert d["sufficiency"] == "conflicted"
    assert d["evidences"] == ["ev_1", "ev_2"]
    assert d["contradictions"] == ["ev_3"]
    assert d["next_step"] == "handoff_to_human"


def test_audit_record_to_dict():
    ar = AuditRecord(
        query="test query",
        hypothesis_id="ih_123",
        boundary_checked=True,
        channels_used=["vector", "graph"],
        discarded_candidates=5,
        discard_reasons=["out_of_boundary", "stale_version"],
        stop_reason="evidence_sufficient",
        fusion_strategy="rrf_v2",
        total_time_ms=150,
    )
    d = ar.to_dict()
    assert d["query"] == "test query"
    assert d["boundary_checked"] is True
    assert d["channels_used"] == ["vector", "graph"]
    assert d["discarded_candidates"] == 5
    assert d["stop_reason"] == "evidence_sufficient"


def test_evidence_search_response_to_dict():
    ar = AuditRecord(query="test", hypothesis_id="ih_1")
    es = EvidenceSet(hypothesis_id="ih_1", evidences=["ev_1"])
    resp = EvidenceSearchResponse(evidence_set=es, audit=ar)
    d = resp.to_dict()
    assert "evidence_set" in d
    assert "audit" in d
    assert d["evidence_set"]["hypothesis_id"] == "ih_1"


def test_boundary_defaults():
    b = Boundary(root_id="kb_test")
    assert b.root_id == "kb_test"
    assert b.role_scope == []
    assert b.ontology_scope == {}
    assert b.lifecycle_scope == []
    assert b.usage_scope == []
    assert b.max_hops == 2
    assert b.max_top_k == 10
    assert b.time_budget_ms == 2000


def test_boundary_to_dict():
    b = Boundary(
        root_id="kb_abc",
        role_scope=["admin"],
        ontology_scope={"domain": ["quality"]},
        lifecycle_scope=["active"],
        usage_scope=["knowledge_answer"],
        max_hops=3,
        max_top_k=20,
    )
    d = b.to_dict()
    assert d["root_id"] == "kb_abc"
    assert d["role_scope"] == ["admin"]
    assert d["max_hops"] == 3
    assert d["max_top_k"] == 20


def test_hypothesis_auto_id():
    h = Hypothesis(statement="test hypothesis")
    assert h.hypothesis_id is not None
    assert h.hypothesis_id.startswith("ih_")


def test_hypothesis_to_dict():
    h = Hypothesis(
        hypothesis_id="ih_custom",
        statement="user wants to find batch supplier",
        candidate_anchors=["batch_id", "supplier_id"],
        required_evidence_types=["graph_relation", "source_chunk"],
        falsifiable_by=["no batch found", "cross boundary"],
    )
    d = h.to_dict()
    assert d["hypothesis_id"] == "ih_custom"
    assert d["candidate_anchors"] == ["batch_id", "supplier_id"]
    assert "graph_relation" in d["required_evidence_types"]


def test_inquiry_plan_defaults():
    ip = InquiryPlan()
    assert ip.plan_id is not None
    assert ip.plan_id.startswith("ip_")
    assert ip.strategy == InquiryStrategy.HYBRID
    assert "vector" in ip.allowed_channels
    assert "graph" in ip.allowed_channels
    assert "evidence_sufficient" in ip.stop_when


def test_inquiry_plan_to_dict():
    ip = InquiryPlan(
        plan_id="ip_custom",
        strategy=InquiryStrategy.GRAPH_FIRST,
        sub_questions=["which batch?", "which supplier?"],
        allowed_channels=["graph"],
        stop_when=["evidence_sufficient"],
    )
    d = ip.to_dict()
    assert d["plan_id"] == "ip_custom"
    assert d["strategy"] == "graph_first"
    assert d["allowed_channels"] == ["graph"]


def test_context_signals_defaults():
    cs = ContextSignals()
    assert cs.recent_action_trail == []
    assert cs.active_page is None
    assert cs.current_working_set == []


def test_context_signals_to_dict():
    cs = ContextSignals(
        active_page="SchemaPage",
        active_table="產品主檔",
        candidate_anchors=["item_id", "supplier_id"],
    )
    d = cs.to_dict()
    assert d["active_page"] == "SchemaPage"
    assert d["active_table"] == "產品主檔"
    assert "item_id" in d["candidate_anchors"]


def test_evidence_search_request_to_dict():
    b = Boundary(root_id="kb_test")
    h = Hypothesis(statement="test", hypothesis_id="ih_1")
    ip = InquiryPlan(strategy=InquiryStrategy.HYBRID)
    req = EvidenceSearchRequest(
        boundary=b,
        hypothesis=h,
        inquiry_plan=ip,
        query="test query",
    )
    d = req.to_dict()
    assert d["boundary"]["root_id"] == "kb_test"
    assert d["hypothesis"]["hypothesis_id"] == "ih_1"
    assert d["inquiry_plan"]["strategy"] == "hybrid"
    assert d["query"] == "test query"


def test_source_type_enum_values():
    assert SourceType.VECTOR.value == "vector"
    assert SourceType.GRAPH.value == "graph"
    assert SourceType.RAW.value == "raw"
    assert SourceType.FUSION.value == "fusion"


def test_boundary_status_enum_values():
    assert BoundaryStatus.WITHIN_BOUNDARY.value == "within_boundary"
    assert BoundaryStatus.BOUNDARY_UNCLEAR.value == "boundary_unclear"
    assert BoundaryStatus.OUT_OF_BOUNDARY.value == "out_of_boundary"


def test_sufficiency_enum_values():
    assert Sufficiency.SUFFICIENT.value == "sufficient"
    assert Sufficiency.INSUFFICIENT.value == "insufficient"
    assert Sufficiency.CONFLICTED.value == "conflicted"


def test_next_step_enum_values():
    assert NextStep.ASK_FOR_CLARIFICATION.value == "ask_for_clarification"
    assert NextStep.EXPAND_GRAPH.value == "expand_graph"
    assert NextStep.STOP.value == "stop"
    assert NextStep.HANDOFF_TO_HUMAN.value == "handoff_to_human"


def test_inquiry_decomposer_decompose():
    from knowledge_agent.hybrid_rag.inquiry_decomposer import InquiryDecomposer
    from knowledge_agent.hybrid_rag.models.inquiry import Boundary, Hypothesis
    decomposer = InquiryDecomposer()
    boundary = Boundary(root_id="kb_test", max_hops=2, max_top_k=10)
    hypothesis = Hypothesis(
        hypothesis_id="ih_abc",
        statement="使用者可能正在追查退貨批次的上游供應與生產關聯",
        candidate_anchors=["batch_id", "item_id", "supplier_id"],
        required_evidence_types=["graph_relation", "source_chunk"],
        falsifiable_by=["找不到批號對應", "關聯跨越知識邊界"],
    )
    plan = decomposer.decompose(hypothesis, boundary, "查詢退貨批次")
    assert plan.plan_id is not None
    assert plan.plan_id.startswith("ip_")
    assert len(plan.sub_questions) >= 2
    assert "vector" in plan.allowed_channels
    assert "graph" in plan.allowed_channels
    assert "evidence_sufficient" in plan.stop_when
    assert "contradictory_unresolved" in plan.stop_when


def test_inquiry_decomposer_implicit_hypothesis():
    from knowledge_agent.hybrid_rag.inquiry_decomposer import InquiryDecomposer
    from knowledge_agent.hybrid_rag.models.inquiry import Boundary
    decomposer = InquiryDecomposer()
    boundary = Boundary(root_id="kb_test")
    hyp = decomposer.create_implicit_hypothesis(
        "查詢退貨批次和供應商的關聯",
        boundary,
    )
    assert hyp.hypothesis_id is not None
    assert hyp.hypothesis_id.startswith("ih_")
    assert hyp.statement == "查詢退貨批次和供應商的關聯"
    assert "source_chunk" in hyp.required_evidence_types
    assert len(hyp.required_evidence_types) >= 1


def test_inquiry_decomposer_strategy_resolution():
    from knowledge_agent.hybrid_rag.inquiry_decomposer import InquiryDecomposer
    from knowledge_agent.hybrid_rag.models.inquiry import Boundary, Hypothesis, InquiryStrategy
    decomposer = InquiryDecomposer()
    boundary = Boundary(root_id="kb_test")
    hyp_graph = Hypothesis(
        statement="誰供應這個原料？",
        required_evidence_types=["graph_relation"],
        candidate_anchors=["supplier_id"],
    )
    plan = decomposer.decompose(hyp_graph, boundary)
    assert plan.strategy == InquiryStrategy.GRAPH_FIRST
    hyp_vec = Hypothesis(
        statement="這個文件的內容是什麼？",
        required_evidence_types=["source_chunk"],
    )
    plan2 = decomposer.decompose(hyp_vec, boundary)
    assert plan2.strategy == InquiryStrategy.VECTOR_ONLY


def test_state_machine_transitions():
    from knowledge_agent.hybrid_rag.state_machine import (
        HybridRAGState,
        HybridRAGStateMachine,
        compute_next_state,
    )
    sm = HybridRAGStateMachine()
    assert sm.current_state == HybridRAGState.BOUNDARY_CHECKING
    assert sm.is_active() is True
    sm.transition(HybridRAGState.RETRIEVING)
    assert sm.current_state == HybridRAGState.RETRIEVING
    assert len(sm.history) == 1
    sm.transition(HybridRAGState.STOPPED)
    assert sm.is_terminal() is True
    sm.reset()
    assert sm.current_state == HybridRAGState.BOUNDARY_CHECKING


def test_compute_next_state():
    from knowledge_agent.hybrid_rag.state_machine import (
        HybridRAGState,
        compute_next_state,
    )
    assert compute_next_state("out_of_boundary", None, None) == HybridRAGState.STOPPED
    assert compute_next_state("boundary_unclear", None, None) == HybridRAGState.CLARIFY_REQUIRED
    assert compute_next_state(None, "sufficient", None) == HybridRAGState.STOPPED
    assert compute_next_state(None, "conflicted", None) == HybridRAGState.CLARIFY_REQUIRED
    assert compute_next_state(None, None, "stop") == HybridRAGState.STOPPED
    assert compute_next_state(None, None, "handoff_to_human") == HybridRAGState.HANDOFF_REQUIRED
    assert compute_next_state(None, "insufficient", "expand_graph") == HybridRAGState.RETRIEVING
    assert compute_next_state("within_boundary", "insufficient", None, has_hypothesis=False) == HybridRAGState.PLANNING


def test_evidence_analyzer_sufficient():
    from knowledge_agent.hybrid_rag.evidence_analyzer import EvidenceAnalyzer
    from knowledge_agent.hybrid_rag.models.evidence import EvidenceUnit, SourceType
    from knowledge_agent.hybrid_rag.models.inquiry import Hypothesis
    analyzer = EvidenceAnalyzer()
    eu1 = EvidenceUnit(
        evidence_id="ev_1",
        source_type=SourceType.VECTOR,
        content="evidence 1",
        supports=["ih_test"],
    )
    hyp = Hypothesis(hypothesis_id="ih_test", required_evidence_types=["source_chunk"])
    es, gaps = analyzer.analyze([eu1], hyp)
    assert es.sufficiency.value == "sufficient"
    assert es.next_step.value == "stop"
    assert "ev_1" in es.evidences


def test_evidence_analyzer_conflicted():
    from knowledge_agent.hybrid_rag.evidence_analyzer import EvidenceAnalyzer
    from knowledge_agent.hybrid_rag.models.evidence import EvidenceUnit, SourceType
    from knowledge_agent.hybrid_rag.models.inquiry import Hypothesis
    analyzer = EvidenceAnalyzer()
    eu = EvidenceUnit(
        evidence_id="ev_c1",
        source_type=SourceType.VECTOR,
        content="contradiction",
        contradicts=["ih_test"],
    )
    hyp = Hypothesis(hypothesis_id="ih_test")
    es, gaps = analyzer.analyze([eu], hyp)
    assert es.sufficiency.value == "conflicted"
    assert es.next_step.value == "handoff_to_human"
    assert "ev_c1" in es.contradictions


def test_evidence_analyzer_insufficient_with_gaps():
    from knowledge_agent.hybrid_rag.evidence_analyzer import EvidenceAnalyzer
    from knowledge_agent.hybrid_rag.models.evidence import EvidenceUnit, SourceType
    from knowledge_agent.hybrid_rag.models.inquiry import Hypothesis
    analyzer = EvidenceAnalyzer()
    eu = EvidenceUnit(
        evidence_id="ev_partial",
        source_type=SourceType.VECTOR,
        content="partial",
        supports=["ih_test"],
    )
    hyp = Hypothesis(
        hypothesis_id="ih_test",
        required_evidence_types=["source_chunk", "graph_relation"],
    )
    es, gaps = analyzer.analyze([eu], hyp)
    assert es.sufficiency.value == "insufficient"
    assert len(gaps) > 0
    assert "graph_relation" in str(gaps)


def test_boundary_checker_result_properties():
    from knowledge_agent.hybrid_rag.boundary_checker import BoundaryCheckResult
    result = BoundaryCheckResult(
        status="within_boundary",
        passed_checks=["root_id_exists", "role_scope"],
        failed_checks=[],
    )
    assert result.is_within_boundary is True
    assert result.is_boundary_unclear is False
    assert result.is_out_of_boundary is False


def test_boundary_checker_result_out_of_boundary():
    from knowledge_agent.hybrid_rag.boundary_checker import BoundaryCheckResult
    result = BoundaryCheckResult(
        status="out_of_boundary",
        passed_checks=["role_scope"],
        failed_checks=[("root_id", "root_not_found")],
        reason="Boundary rejected: root_not_found",
    )
    assert result.is_out_of_boundary is True
    assert result.is_within_boundary is False
    assert result.is_boundary_unclear is False


def test_boundary_checker_result_boundary_unclear():
    from knowledge_agent.hybrid_rag.boundary_checker import BoundaryCheckResult
    result = BoundaryCheckResult(
        status="boundary_unclear",
        passed_checks=["root_id_exists"],
        failed_checks=[("ontology_scope", "ontology_mismatch")],
        reason="Boundary unclear: ontology_mismatch",
    )
    assert result.is_boundary_unclear is True
    assert result.is_within_boundary is False
    assert result.is_out_of_boundary is False


def test_boundary_checker_class():
    from knowledge_agent.hybrid_rag.boundary_checker import BoundaryChecker
    from knowledge_agent.hybrid_rag.models.inquiry import Boundary
    checker = BoundaryChecker()
    boundary = Boundary(root_id="kb_test", role_scope=["admin"])
    result = checker.check(boundary)
    assert result.status in ("within_boundary", "out_of_boundary", "boundary_unclear")
    assert isinstance(result.passed_checks, list)
    assert isinstance(result.failed_checks, list)


if __name__ == "__main__":
    test_evidence_unit_auto_id()
    test_evidence_unit_to_dict()
    test_evidence_set_defaults()
    test_evidence_set_to_dict()
    test_audit_record_to_dict()
    test_evidence_search_response_to_dict()
    test_boundary_defaults()
    test_boundary_to_dict()
    test_hypothesis_auto_id()
    test_hypothesis_to_dict()
    test_inquiry_plan_defaults()
    test_inquiry_plan_to_dict()
    test_context_signals_defaults()
    test_context_signals_to_dict()
    test_evidence_search_request_to_dict()
    test_source_type_enum_values()
    test_boundary_status_enum_values()
    test_sufficiency_enum_values()
    test_next_step_enum_values()
    test_inquiry_decomposer_decompose()
    test_inquiry_decomposer_implicit_hypothesis()
    test_inquiry_decomposer_strategy_resolution()
    test_state_machine_transitions()
    test_compute_next_state()
    test_evidence_analyzer_sufficient()
    test_evidence_analyzer_conflicted()
    test_evidence_analyzer_insufficient_with_gaps()
    test_boundary_checker_result_properties()
    test_boundary_checker_result_out_of_boundary()
    test_boundary_checker_result_boundary_unclear()
    test_boundary_checker_class()
    print("All HybridRAG v2 model tests passed.")
