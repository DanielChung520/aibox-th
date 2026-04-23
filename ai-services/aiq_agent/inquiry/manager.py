"""
@file        Inquiry Layer Manager
@description 管理 Inquiry 狀態、LLM 分析與決策流程。
@lastUpdate  2026-04-18 19:34:34
@author      Daniel Chung
@version     1.0.0
"""

from __future__ import annotations

import math
import os
import threading
import time
from uuid import uuid4

from aiq_agent.inquiry.boundary import check_escalation, evaluate_boundary
from aiq_agent.inquiry.llm_client import InquiryLLMClient
from aiq_agent.inquiry.models import (
    BoundaryStatus,
    BoundaryStatusEnum,
    ClarificationAnswer,
    Evidence,
    Hypothesis,
    InquiryDecision,
    InquiryRequest,
    InquiryResult,
    InquiryState,
    LLMAnalysisRequest,
)
from aiq_agent.perception.models import WorkingContext


MAX_INQUIRY_STATES = int(os.environ.get("AIQ_MAX_INQUIRY_STATES", "500"))
INQUIRY_STATE_TTL = int(os.environ.get("AIQ_INQUIRY_STATE_TTL", "3600"))


class InquiryManager:
    """Stateful inquiry manager for the AIQ inquiry layer."""

    def __init__(self, gap_threshold: float = 0.3) -> None:
        """Initialize the inquiry manager."""
        self._states: dict[str, InquiryState] = {}
        self._timestamps: dict[str, float] = {}
        self._lock = threading.Lock()
        self._llm_client = InquiryLLMClient()
        self._gap_threshold = gap_threshold

    async def process_inquiry(
        self,
        user_key: str,
        working_context: WorkingContext,
        request: InquiryRequest,
    ) -> InquiryResult:
        """Process an inquiry request and return the latest decision."""
        state = self._get_or_create_state(user_key)

        if request.clarification_answers:
            self._apply_clarification_answers(state, request.clarification_answers)

        llm_request = LLMAnalysisRequest(
            working_context_json=working_context.model_dump_json(),
            query=request.query,
            candidate_seeds=_candidate_seeds_from_context(working_context),
        )
        llm_response = await self._llm_client.analyze(llm_request)

        merged_hypotheses = self._merge_hypotheses(state.hypotheses, llm_response.hypotheses)
        boundary = evaluate_boundary(merged_hypotheses, working_context)
        escalation_reason = check_escalation(merged_hypotheses, boundary)

        updated_state = state.model_copy(deep=True)
        updated_state.hypotheses = merged_hypotheses
        updated_state.boundary_status = boundary
        updated_state.last_update = int(time.time())

        if not merged_hypotheses:
            self._store_state(user_key, updated_state)
            return InquiryResult(decision=InquiryDecision.STAY, state=updated_state)

        gap = _confidence_gap(merged_hypotheses)
        clarification_questions = _select_clarification_questions(
            llm_response.suggested_questions,
            boundary,
        )

        if escalation_reason is not None:
            self._store_state(user_key, updated_state)
            return InquiryResult(
                decision=InquiryDecision.ESCALATE,
                state=updated_state,
                escalation_reason=escalation_reason,
            )

        if gap > self._gap_threshold and boundary.status == BoundaryStatusEnum.SUFFICIENT:
            committed_hypothesis = merged_hypotheses[0]
            self._store_state(user_key, updated_state)
            return InquiryResult(
                decision=InquiryDecision.COMMIT,
                state=updated_state,
                committed_hypothesis=committed_hypothesis,
            )

        if (
            boundary.status == BoundaryStatusEnum.INSUFFICIENT
            and updated_state.clarification_round < updated_state.max_clarification_rounds
        ):
            updated_state.clarification_round += 1
            self._store_state(user_key, updated_state)
            return InquiryResult(
                decision=InquiryDecision.CLARIFY,
                state=updated_state,
                clarification_questions=clarification_questions,
            )

        self._store_state(user_key, updated_state)
        return InquiryResult(decision=InquiryDecision.STAY, state=updated_state)

    def get_state(self, user_key: str) -> InquiryState | None:
        """Return a copy of the inquiry state for a user."""
        with self._lock:
            state = self._states.get(user_key)
            return state.model_copy(deep=True) if state is not None else None

    def reset_state(self, user_key: str) -> None:
        """Reset inquiry state for a user."""
        with self._lock:
            self._states.pop(user_key, None)
            self._timestamps.pop(user_key, None)

    def _evict_stale(self) -> None:
        """Remove expired and excess states (must be called under lock)."""
        now = time.monotonic()
        stale = [k for k, ts in self._timestamps.items() if now - ts > INQUIRY_STATE_TTL]
        for k in stale:
            self._states.pop(k, None)
            self._timestamps.pop(k, None)
        if len(self._states) > MAX_INQUIRY_STATES:
            oldest = sorted(self._timestamps, key=lambda k: self._timestamps[k])
            for k in oldest[: len(self._states) - MAX_INQUIRY_STATES]:
                self._states.pop(k, None)
                self._timestamps.pop(k, None)

    def _get_or_create_state(self, user_key: str) -> InquiryState:
        """Get or create the state for a given user key."""
        with self._lock:
            self._evict_stale()
            existing_state = self._states.get(user_key)
            if existing_state is not None:
                self._timestamps[user_key] = time.monotonic()
                return existing_state.model_copy(deep=True)

            timestamp = int(time.time())
            state = InquiryState(
                prediction_id=str(uuid4()),
                hypotheses=[],
                boundary_status=BoundaryStatus(status=BoundaryStatusEnum.INSUFFICIENT),
                user_key=user_key,
                last_update=timestamp,
            )
            self._states[user_key] = state
            self._timestamps[user_key] = time.monotonic()
            return state.model_copy(deep=True)

    def _store_state(self, user_key: str, state: InquiryState) -> None:
        """Persist the latest inquiry state."""
        with self._lock:
            self._states[user_key] = state.model_copy(deep=True)
            self._timestamps[user_key] = time.monotonic()

    def _apply_clarification_answers(
        self,
        state: InquiryState,
        answers: list[ClarificationAnswer],
    ) -> None:
        """Add clarification evidence to current hypotheses."""
        timestamp = int(time.time())
        for hypothesis in state.hypotheses:
            for answer in answers:
                hypothesis.evidence_chain.append(
                    Evidence(
                        source="clarification",
                        signal=f"Q: {answer.question} | A: {answer.answer}",
                        contribution=0.2,
                        timestamp=timestamp,
                    )
                )
            if answers:
                hypothesis.confidence = min(1.0, hypothesis.confidence + 0.05)

    def _merge_hypotheses(
        self,
        existing: list[Hypothesis],
        incoming: list[Hypothesis],
    ) -> list[Hypothesis]:
        """Merge existing and incoming hypotheses, keeping the top three."""
        merged: dict[str, Hypothesis] = {}
        for hypothesis in existing + incoming:
            key = _hypothesis_key(hypothesis)
            current = merged.get(key)
            if current is None:
                merged[key] = hypothesis.model_copy(deep=True)
                continue

            merged[key] = _combine_hypotheses(current, hypothesis)

        ranked = sorted(merged.values(), key=lambda item: item.confidence, reverse=True)
        return ranked[:3]


def _candidate_seeds_from_context(working_context: WorkingContext) -> list[str]:
    """Extract candidate seeds from the working context anchors."""
    seeds: list[str] = []
    for anchor in working_context.active_anchors:
        if anchor.value not in seeds:
            seeds.append(anchor.value)
    return seeds[:5]


def _hypothesis_key(hypothesis: Hypothesis) -> str:
    """Build a stable merge key for a hypothesis."""
    return f"{hypothesis.intent_label}:{hypothesis.execution_path.value}"


def _combine_hypotheses(left: Hypothesis, right: Hypothesis) -> Hypothesis:
    """Combine two hypotheses representing the same intent candidate."""
    evidence_lookup: dict[tuple[str, str, int], Evidence] = {}
    for evidence in left.evidence_chain + right.evidence_chain:
        evidence_lookup[(evidence.source, evidence.signal, evidence.timestamp)] = evidence

    parameters = left.parameters.copy()
    parameters.update(right.parameters)
    winner = right if right.confidence >= left.confidence else left

    return Hypothesis(
        id=winner.id,
        intent_label=winner.intent_label,
        execution_path=winner.execution_path,
        confidence=max(left.confidence, right.confidence),
        evidence_chain=list(evidence_lookup.values()),
        parameters=parameters,
    )


def _confidence_gap(hypotheses: list[Hypothesis]) -> float:
    """Return confidence gap between top hypotheses."""
    if not hypotheses:
        return 0.0
    if len(hypotheses) == 1:
        return math.inf

    ranked = sorted(hypotheses, key=lambda item: item.confidence, reverse=True)
    return ranked[0].confidence - ranked[1].confidence


def _select_clarification_questions(
    llm_questions: list[str],
    boundary: BoundaryStatus,
) -> list[str]:
    """Select up to two clarification questions for the current round."""
    questions: list[str] = []
    for question in llm_questions + boundary.suggested_questions:
        if question and question not in questions:
            questions.append(question)
        if len(questions) == 2:
            break
    return questions
