"""
HybridRAG v2 Inquiry Models — Boundary, Hypothesis, InquiryPlan, ContextSignals.

These models implement the bounded evidence assembly input contracts
defined in HybridRAG-細部規格書-v2.md Section 4.1.

@lastUpdate: 2026-04-18 00:43:35
@author: Daniel Chung
@version: 2.0.0
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class InquiryStrategy(str, Enum):
    HYBRID = "hybrid"
    VECTOR_FIRST = "vector_first"
    GRAPH_FIRST = "graph_first"
    VECTOR_ONLY = "vector_only"
    GRAPH_ONLY = "graph_only"


@dataclass
class Boundary:
    root_id: str
    allowed_roles: list[str] = field(default_factory=list)
    ontology_scope: dict[str, list[str]] = field(default_factory=dict)
    lifecycle_scope: list[str] = field(default_factory=list)
    usage_scope: list[str] = field(default_factory=list)
    max_hops: int = 2
    max_top_k: int = 10
    time_budget_ms: int = 2000

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_id": self.root_id,
            "allowed_roles": self.allowed_roles,
            "ontology_scope": self.ontology_scope,
            "lifecycle_scope": self.lifecycle_scope,
            "usage_scope": self.usage_scope,
            "max_hops": self.max_hops,
            "max_top_k": self.max_top_k,
            "time_budget_ms": self.time_budget_ms,
        }


@dataclass
class Hypothesis:
    hypothesis_id: str | None = None
    statement: str = ""
    candidate_anchors: list[str] = field(default_factory=list)
    required_evidence_types: list[str] = field(default_factory=list)
    falsifiable_by: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.hypothesis_id is None:
            self.hypothesis_id = f"ih_{uuid.uuid4().hex[:12]}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "statement": self.statement,
            "candidate_anchors": self.candidate_anchors,
            "required_evidence_types": self.required_evidence_types,
            "falsifiable_by": self.falsifiable_by,
        }


@dataclass
class InquiryPlan:
    plan_id: str | None = None
    strategy: InquiryStrategy = InquiryStrategy.HYBRID
    sub_questions: list[str] = field(default_factory=list)
    allowed_channels: list[str] = field(default_factory=lambda: ["vector", "graph", "raw"])
    stop_when: list[str] = field(
        default_factory=lambda: [
            "evidence_sufficient",
            "boundary_unclear",
            "budget_exhausted",
        ]
    )

    def __post_init__(self) -> None:
        if self.plan_id is None:
            self.plan_id = f"ip_{uuid.uuid4().hex[:12]}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "strategy": self.strategy.value,
            "sub_questions": self.sub_questions,
            "allowed_channels": self.allowed_channels,
            "stop_when": self.stop_when,
        }


@dataclass
class ContextSignals:
    recent_action_trail: list[dict[str, Any]] = field(default_factory=list)
    active_page: str | None = None
    active_table: str | None = None
    active_row: dict[str, Any] | None = None
    active_field: str | None = None
    current_working_set: list[str] = field(default_factory=list)
    candidate_anchors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "recent_action_trail": self.recent_action_trail,
            "active_page": self.active_page,
            "active_table": self.active_table,
            "active_row": self.active_row,
            "active_field": self.active_field,
            "current_working_set": self.current_working_set,
            "candidate_anchors": self.candidate_anchors,
        }


@dataclass
class EvidenceSearchRequest:
    boundary: Boundary
    hypothesis: Hypothesis
    inquiry_plan: InquiryPlan | None = None
    context_signals: ContextSignals | None = None
    query: str = ""
    user_role: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "boundary": self.boundary.to_dict(),
            "hypothesis": self.hypothesis.to_dict(),
            "inquiry_plan": self.inquiry_plan.to_dict() if self.inquiry_plan else None,
            "context_signals": self.context_signals.to_dict() if self.context_signals else None,
            "query": self.query,
            "user_role": self.user_role,
        }
