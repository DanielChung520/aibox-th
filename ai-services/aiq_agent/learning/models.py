"""
@file        Learning Layer 資料模型
@description 定義 AIQ Learning Layer 的 UserProfileSummary 與 turn-complete 請求模型。
@lastUpdate  2026-04-18 20:12:44
@author      Daniel Chung
@version     1.0.0
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

class Pattern(BaseModel):
    """Aggregated learning pattern summary for a specific context signature."""

    context_signature: str
    execution_path: str
    success_rate: float
    sample_count: int


class QueryPatterns(BaseModel):
    """Query-related preference summary derived from completed turns."""

    frequent_intents: list[str] = Field(default_factory=list)
    avg_clarification_rounds: float = 0.0
    preferred_response_depth: Literal["brief", "detailed"] = "brief"


class UserProfileSummary(BaseModel):
    """Per-user learning summary persisted in ArangoDB."""

    user_key: str
    last_updated: int
    total_turns: int = 0
    domain_counts: dict[str, int] = Field(default_factory=dict)
    domain_distribution: dict[str, float] = Field(default_factory=dict)
    query_patterns: QueryPatterns = Field(default_factory=QueryPatterns)
    success_patterns: list[Pattern] = Field(default_factory=list)
    failure_patterns: list[Pattern] = Field(default_factory=list)


class TurnCompleteRequest(BaseModel):
    """Request payload emitted when an AIQ turn is completed."""

    prediction_id: str
    execution_path: str
    outcome: str
    clarification_rounds: int = 0
    context_signature: str = ""
    domain: str = ""


__all__ = [
    "Pattern",
    "QueryPatterns",
    "TurnCompleteRequest",
    "UserProfileSummary",
]
