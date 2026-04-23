"""
HybridRAG v2 State Machine — 狀態機定義與轉換邏輯.

依據 HybridRAG-細部規格書-v2.md Section 5 狀態機定義。

狀態：
- boundary_checking
- planning
- retrieving
- assembling
- evaluating
- stopped
- clarify_required
- handoff_required

@lastUpdate: 2026-04-18 00:43:35
@author: Daniel Chung
@version: 2.0.0
"""

from __future__ import annotations

from enum import Enum


class HybridRAGState(str, Enum):
    BOUNDARY_CHECKING = "boundary_checking"
    PLANNING = "planning"
    RETRIEVING = "retrieving"
    ASSEMBLING = "assembling"
    EVALUATING = "evaluating"
    STOPPED = "stopped"
    CLARIFY_REQUIRED = "clarify_required"
    HANDOFF_REQUIRED = "handoff_required"


class HybridRAGStateMachine:
    def __init__(self) -> None:
        self._state: HybridRAGState = HybridRAGState.BOUNDARY_CHECKING
        self._history: list[HybridRAGState] = []

    @property
    def current_state(self) -> HybridRAGState:
        return self._state

    @property
    def history(self) -> list[HybridRAGState]:
        return list(self._history)

    def transition(self, new_state: HybridRAGState) -> None:
        if new_state != self._state:
            self._history.append(self._state)
            self._state = new_state

    def is_terminal(self) -> bool:
        return self._state in (HybridRAGState.STOPPED, HybridRAGState.CLARIFY_REQUIRED, HybridRAGState.HANDOFF_REQUIRED)

    def is_active(self) -> bool:
        return not self.is_terminal()

    def reset(self) -> None:
        self._state = HybridRAGState.BOUNDARY_CHECKING
        self._history = []


def compute_next_state(
    boundary_status: str | None,
    sufficiency: str | None,
    next_step: str | None,
    has_hypothesis: bool = True,
) -> HybridRAGState:
    if boundary_status == "out_of_boundary":
        return HybridRAGState.STOPPED
    if boundary_status == "boundary_unclear":
        return HybridRAGState.CLARIFY_REQUIRED
    if next_step == "handoff_to_human":
        return HybridRAGState.HANDOFF_REQUIRED
    if next_step == "ask_for_clarification":
        return HybridRAGState.CLARIFY_REQUIRED
    if next_step == "stop":
        return HybridRAGState.STOPPED
    if sufficiency == "sufficient":
        return HybridRAGState.STOPPED
    if sufficiency == "conflicted":
        return HybridRAGState.CLARIFY_REQUIRED
    if not has_hypothesis:
        return HybridRAGState.PLANNING
    return HybridRAGState.RETRIEVING
