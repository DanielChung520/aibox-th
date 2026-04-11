"""
@file        multi_step_orchestrator.py
@description N-step chained query orchestrator for cross-table Ragic queries.
             Uses knowledge graph traversal to discover related tables and
             chains step executions iteratively with cycle detection.
@lastUpdate  2026-04-11 22:35:00
@author      Daniel Chung
@version     1.1.0
"""

from __future__ import annotations

import logging
import time
from typing import Protocol, runtime_checkable

from data_agent.ragic.models_phase9 import (
    GraphQueryResult,
    MultiStepQuery,
    MultiStepResult,
    StepResult,
)

logger = logging.getLogger(__name__)


@runtime_checkable
class StepExecutorLike(Protocol):
    async def execute(
        self, request: MultiStepQuery | StepResult
    ) -> StepResult: ...


@runtime_checkable
class GraphQueryLike(Protocol):
    async def get_related_tables(
        self, table_name: str, account: str
    ) -> GraphQueryResult: ...


class MultiStepOrchestrator:

    def __init__(
        self,
        graph_query: GraphQueryLike,
        step_executor: StepExecutorLike,
        result_merger: object,
    ) -> None:
        self._graph = graph_query
        self._executor = step_executor
        self._merger = result_merger

    async def execute(self, request: MultiStepQuery) -> MultiStepResult:
        start = time.monotonic()
        steps: list[StepResult] = []
        errors: list[str] = []
        visited: set[str] = set()
        partial_failure = False

        primary_step = await self._execute_primary(
            request, start, steps, errors
        )
        if primary_step is None:
            return self._build_result(request, steps, errors, start, True)

        primary_table = primary_step.table_name
        visited.add(primary_table)

        if primary_step.error is not None:
            partial_failure = True

        tables_to_explore = [primary_table]
        step_index = 1

        while tables_to_explore and step_index < request.max_steps:
            if self._is_timed_out(start, request.total_timeout_s):
                partial_failure = True
                errors.append("Total timeout exceeded")
                break

            current_table = tables_to_explore.pop(0)
            related = await self._get_related_safe(
                current_table, request.account
            )

            fan_out_count = 0
            for related_table in related:
                if step_index >= request.max_steps:
                    partial_failure = True
                    break
                if related_table in visited:
                    continue
                if fan_out_count >= request.max_fan_out:
                    break

                visited.add(related_table)
                fan_out_count += 1

                if self._is_timed_out(start, request.total_timeout_s):
                    partial_failure = True
                    errors.append("Total timeout exceeded")
                    break

                dep_step = await self._execute_dependent(
                    step_index, related_table, request, start
                )
                steps.append(dep_step)

                if dep_step.error is not None:
                    partial_failure = True
                    errors.append(
                        f"Step {step_index} ({related_table}): {dep_step.error}"
                    )

                tables_to_explore.append(related_table)
                step_index += 1

        if step_index >= request.max_steps and tables_to_explore:
            partial_failure = True

        return self._build_result(
            request, steps, errors, start, partial_failure
        )

    async def _execute_primary(
        self,
        request: MultiStepQuery,
        start: float,
        steps: list[StepResult],
        errors: list[str],
    ) -> StepResult | None:
        try:
            step = await self._executor.execute(request)
        except TimeoutError:
            elapsed = (time.monotonic() - start) * 1000
            error_step = StepResult(
                step_index=0,
                table_name=request.query,
                execution_time_ms=round(elapsed, 2),
                error="Primary step timeout",
            )
            steps.append(error_step)
            errors.append("Step 0: Primary step timeout")
            return None
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            error_step = StepResult(
                step_index=0,
                table_name=request.query,
                execution_time_ms=round(elapsed, 2),
                error=str(exc),
            )
            steps.append(error_step)
            errors.append(f"Step 0: {exc}")
            return None

        steps.append(step)
        if step.error is not None:
            errors.append(f"Step 0 ({step.table_name}): {step.error}")
        return step

    async def _execute_dependent(
        self,
        step_index: int,
        table_name: str,
        request: MultiStepQuery,
        start: float,
    ) -> StepResult:
        try:
            return await self._executor.execute(
                StepResult(
                    step_index=step_index,
                    table_name=table_name,
                )
            )
        except TimeoutError:
            elapsed = (time.monotonic() - start) * 1000
            return StepResult(
                step_index=step_index,
                table_name=table_name,
                execution_time_ms=round(elapsed, 2),
                error="Step timeout exceeded",
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return StepResult(
                step_index=step_index,
                table_name=table_name,
                execution_time_ms=round(elapsed, 2),
                error=str(exc),
            )

    async def _get_related_safe(
        self, table_name: str, account: str
    ) -> list[str]:
        try:
            result = await self._graph.get_related_tables(
                table_name, account
            )
            return [r.target_table for r in result.relations]
        except Exception as exc:
            logger.warning("Graph query failed for %s: %s", table_name, exc)
            return []

    @staticmethod
    def _is_timed_out(start: float, total_timeout_s: float) -> bool:
        return (time.monotonic() - start) > total_timeout_s

    @staticmethod
    def _build_result(
        request: MultiStepQuery,
        steps: list[StepResult],
        errors: list[str],
        start: float,
        partial_failure: bool,
    ) -> MultiStepResult:
        elapsed = (time.monotonic() - start) * 1000
        total_records = sum(s.record_count for s in steps)
        return MultiStepResult(
            query=request.query,
            steps=steps,
            total_steps=len(steps),
            total_records=total_records,
            total_time_ms=round(elapsed, 2),
            partial_failure=partial_failure,
            errors=errors,
        )
