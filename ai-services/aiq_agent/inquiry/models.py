"""
@file        Inquiry Layer 資料模型
@description Hypothesis, Evidence, BoundaryStatus, InquiryState, ExecutionPath
@lastUpdate  2026-04-18 19:34:34
@author      Daniel Chung
@version     1.0.0
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class ExecutionPath(str, Enum):
    """Normalized execution paths for committed inquiry hypotheses."""

    KNOWLEDGE_SEARCH = "knowledge_search"
    OPERATION_GUIDE = "operation_guide"
    ROUTE_TO_DATA = "route_to_data"
    TODO_GENERATE = "todo_generate"
    LLM_ANSWER = "llm_answer"
    WEB_FALLBACK = "web_fallback"
    TOOL_CALL = "tool_call"


class Evidence(BaseModel):
    """Evidence item supporting an inquiry hypothesis."""

    source: Literal["anchor", "query", "behavior", "clarification", "user_profile"]
    signal: str
    contribution: float = Field(ge=0.0, le=1.0)
    timestamp: int


class Hypothesis(BaseModel):
    """Candidate intent hypothesis for inquiry resolution."""

    id: str
    intent_label: str
    execution_path: ExecutionPath
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_chain: list[Evidence] = Field(default_factory=list)
    parameters: dict[str, object] = Field(default_factory=dict)


class BoundaryStatusEnum(str, Enum):
    """Boundary sufficiency classification."""

    SUFFICIENT = "sufficient"
    INSUFFICIENT = "insufficient"
    OUT_OF_SCOPE = "out_of_scope"


class BoundaryStatus(BaseModel):
    """Boundary assessment result for current inquiry state."""

    status: BoundaryStatusEnum
    missing_dimensions: list[str] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list)


class InquiryState(BaseModel):
    """Per-user inquiry state maintained across clarification rounds."""

    prediction_id: str
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    boundary_status: BoundaryStatus
    clarification_round: int = 0
    max_clarification_rounds: int = 3
    user_key: str
    last_update: int


class InquiryDecision(str, Enum):
    """Decision emitted by the inquiry manager."""

    COMMIT = "commit"
    CLARIFY = "clarify"
    STAY = "stay"
    ESCALATE = "escalate"


class InquiryResult(BaseModel):
    """Inquiry processing result returned by the API layer."""

    decision: InquiryDecision
    state: InquiryState
    committed_hypothesis: Hypothesis | None = None
    clarification_questions: list[str] = Field(default_factory=list)
    escalation_reason: str | None = None


class LLMAnalysisRequest(BaseModel):
    """Structured request sent to the inquiry LLM analyzer."""

    working_context_json: str
    query: str | None = None
    candidate_seeds: list[str] = Field(default_factory=list)


class LLMAnalysisResponse(BaseModel):
    """Structured response parsed from the inquiry LLM output."""

    hypotheses: list[Hypothesis]
    boundary_status: BoundaryStatus
    suggested_questions: list[str] = Field(default_factory=list)
    reasoning: str = ""


class ClarificationAnswer(BaseModel):
    """User answer for a clarification question."""

    question: str
    answer: str


class InquiryRequest(BaseModel):
    """Request body for inquiry analysis."""

    query: str | None = None
    clarification_answers: list[ClarificationAnswer] = Field(default_factory=list)
