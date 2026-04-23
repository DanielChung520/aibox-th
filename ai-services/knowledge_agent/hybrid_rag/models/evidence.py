"""
HybridRAG v2 Evidence Models — EvidenceUnit, EvidenceSet, AuditRecord.

These models implement the bounded evidence assembly output contracts
defined in HybridRAG-細部規格書-v2.md Section 4.2.

@lastUpdate: 2026-04-18 00:43:35
@author: Daniel Chung
@version: 2.0.0
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum


# Source Type


class SourceType(str, Enum):
    VECTOR = "vector"
    GRAPH = "graph"
    RAW = "raw"
    FUSION = "fusion"


@dataclass
class EvidenceProvenance:
    text_span: dict[str, int] | None = None
    ontology_version: str | None = None
    lifecycle_status: str | None = None


# ---------------------------------------------------------------------------
# EvidenceUnit
# ---------------------------------------------------------------------------


@dataclass
class EvidenceUnit:
    evidence_id: str | None = None
    source_type: SourceType = SourceType.VECTOR
    root_id: str | None = None
    file_id: str | None = None
    chunk_index: int | None = None
    entity_id: str | None = None
    content: str = ""
    normalized_score: float = 0.0
    extraction_confidence: float = 0.0
    supports: list[str] = field(default_factory=list)
    contradicts: list[str] = field(default_factory=list)
    provenance: EvidenceProvenance = field(default_factory=EvidenceProvenance)

    def __post_init__(self) -> None:
        if self.evidence_id is None:
            self.evidence_id = f"ev_{uuid.uuid4().hex[:12]}"

    def to_dict(self) -> dict[str, object]:
        return {
            "evidence_id": self.evidence_id,
            "source_type": self.source_type.value,
            "root_id": self.root_id,
            "file_id": self.file_id,
            "chunk_index": self.chunk_index,
            "entity_id": self.entity_id,
            "content": self.content,
            "normalized_score": round(self.normalized_score, 4),
            "extraction_confidence": round(self.extraction_confidence, 4),
            "supports": self.supports,
            "contradicts": self.contradicts,
            "provenance": {
                "text_span": self.provenance.text_span,
                "ontology_version": self.provenance.ontology_version,
                "lifecycle_status": self.provenance.lifecycle_status,
            },
        }


class BoundaryStatus(str, Enum):
    WITHIN_BOUNDARY = "within_boundary"
    BOUNDARY_UNCLEAR = "boundary_unclear"
    OUT_OF_BOUNDARY = "out_of_boundary"


class Sufficiency(str, Enum):
    SUFFICIENT = "sufficient"
    INSUFFICIENT = "insufficient"
    CONFLICTED = "conflicted"


class NextStep(str, Enum):
    ASK_FOR_CLARIFICATION = "ask_for_clarification"
    EXPAND_GRAPH = "expand_graph"
    STOP = "stop"
    HANDOFF_TO_HUMAN = "handoff_to_human"


@dataclass
class EvidenceSet:
    hypothesis_id: str
    boundary_status: BoundaryStatus = BoundaryStatus.WITHIN_BOUNDARY
    sufficiency: Sufficiency = Sufficiency.INSUFFICIENT
    evidences: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    next_step: NextStep = NextStep.STOP

    def to_dict(self) -> dict[str, object]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "boundary_status": self.boundary_status.value,
            "sufficiency": self.sufficiency.value,
            "evidences": self.evidences,
            "contradictions": self.contradictions,
            "gaps": self.gaps,
            "next_step": self.next_step.value,
        }


@dataclass
class AuditRecord:
    query: str = ""
    hypothesis_id: str | None = None
    boundary_checked: bool = False
    channels_used: list[str] = field(default_factory=list)
    discarded_candidates: int = 0
    discard_reasons: list[str] = field(default_factory=list)
    stop_reason: str | None = None
    fusion_strategy: str = "rrf_v2"
    total_time_ms: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "query": self.query,
            "hypothesis_id": self.hypothesis_id,
            "boundary_checked": self.boundary_checked,
            "channels_used": self.channels_used,
            "discarded_candidates": self.discarded_candidates,
            "discard_reasons": self.discard_reasons,
            "stop_reason": self.stop_reason,
            "fusion_strategy": self.fusion_strategy,
            "total_time_ms": self.total_time_ms,
        }


@dataclass
class EvidenceSearchResponse:
    evidence_set: EvidenceSet
    audit: AuditRecord

    def to_dict(self) -> dict[str, object]:
        return {
            "evidence_set": self.evidence_set.to_dict(),
            "audit": self.audit.to_dict(),
        }
