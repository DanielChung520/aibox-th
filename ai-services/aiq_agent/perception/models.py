"""
Pydantic models for AIQ Agent perception state.

@lastUpdate  2026-04-18 22:12:08
@author      Daniel Chung
@version     1.0.0
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SignalEvent(BaseModel):
    """A normalized frontend signal event."""

    type: str
    timestamp: int
    page: str
    meta: dict[str, object] = Field(default_factory=dict)


class SignalPushRequest(BaseModel):
    """Batch request for pushing signal events."""

    signals: list[SignalEvent]


class Anchor(BaseModel):
    """An active anchor inferred from user signals."""

    anchor_type: str
    value: str
    confidence: float
    source: str
    timestamp: int


class PageContext(BaseModel):
    """Page-level context inferred from the latest structure signal."""

    path: str
    page_name: str
    page_type: str
    domain_name: str | None = None
    table_name: str | None = None
    record_count: int | None = None


class BehaviorSnapshot(BaseModel):
    """Recent user behavior summary."""

    recent_actions: list[SignalEvent] = Field(default_factory=list)
    dwell_hotspots: list[str] = Field(default_factory=list)
    filter_patterns: list[str] = Field(default_factory=list)
    click_counts: dict[str, int] = Field(default_factory=dict)  # page → click count
    recent_searches: list[str] = Field(default_factory=list)  # recent search keywords


class UserPrior(BaseModel):
    """Persisted user prior summary."""

    active_domains: dict[str, float] = Field(default_factory=dict)
    frequent_queries: list[str] = Field(default_factory=list)
    skill_level: str = "intermediate"


class SignalAccumulation(BaseModel):
    """Accumulated signal statistics for the current session."""

    total_signals: int = 0
    last_anchor_change: int = 0
    confidence_trend: list[float] = Field(default_factory=list)


class WorkingContext(BaseModel):
    """Full working context produced by the perception layer."""

    active_anchors: list[Anchor] = Field(default_factory=list)
    page_context: PageContext
    behavior_snapshot: BehaviorSnapshot = Field(default_factory=BehaviorSnapshot)
    user_prior: UserPrior = Field(default_factory=UserPrior)
    signal_accumulation: SignalAccumulation = Field(default_factory=SignalAccumulation)


class CommitContext(BaseModel):
    """Contextual hints forwarded from AIQ working context to downstream agents."""

    page_path: str = ""
    page_name: str = ""
    table_name: str = ""
    domain_name: str = ""
    field_hints: list[str] = Field(default_factory=list)
    active_anchors: list[str] = Field(default_factory=list)


class CommitRequest(BaseModel):
    """Commit request for downstream execution routing."""

    hypothesis_id: str
    execution_path: str
    natural_language: str = ""
    context: CommitContext = Field(default_factory=CommitContext)
