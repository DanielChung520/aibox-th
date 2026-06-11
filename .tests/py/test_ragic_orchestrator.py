"""
@file        test_ragic_orchestrator.py
@description RED phase TDD test skeleton for multi-step RAGIC orchestrator
@lastUpdate  2026-04-11 16:58:26
@author      Daniel Chung
@version     1.0.0
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from data_agent.ragic.models import MultiStepQuery, MultiStepResult, StepResult
from data_agent.ragic.models_phase9 import GraphQueryResult, GraphRelation
from data_agent.ragic.multi_step_orchestrator import MultiStepOrchestrator


@pytest.fixture
def mock_graph_query() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_step_executor() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_result_merger() -> MagicMock:
    return MagicMock()


@pytest.fixture
def orchestrator(
    mock_graph_query: MagicMock,
    mock_step_executor: MagicMock,
    mock_result_merger: MagicMock,
) -> MultiStepOrchestrator:
    return MultiStepOrchestrator(
        graph_query=mock_graph_query,
        step_executor=mock_step_executor,
        result_merger=mock_result_merger,
    )


def _make_step(index: int, table: str, error: str | None = None) -> StepResult:
    return StepResult(
        step_index=index,
        table_key=f"tab/{index}",
        table_name=table,
        records=[{"id": index}] if error is None else [],
        record_count=1 if error is None else 0,
        execution_time_ms=50.0,
        error=error,
    )


def _gqr(table: str, targets: list[str]) -> GraphQueryResult:
    return GraphQueryResult(
        table=table,
        relations=[
            GraphRelation(
                target_table=t, target_field="", source_field="", direction="outgoing"
            )
            for t in targets
        ],
    )


@pytest.mark.asyncio
async def test_single_step_query(
    orchestrator: MultiStepOrchestrator,
    mock_graph_query: MagicMock,
    mock_step_executor: MagicMock,
) -> None:
    query = MultiStepQuery(query="列出所有採購單", account="2025shianyong")
    mock_graph_query.get_related_tables = AsyncMock(return_value=_gqr("採購單", []))
    mock_step_executor.execute = AsyncMock(return_value=_make_step(0, "採購單"))

    result = await orchestrator.execute(query)

    assert len(result.steps) == 1
    assert result.partial_failure is False
    assert result.steps[0].table_name == "採購單"


@pytest.mark.asyncio
async def test_multi_step_chained(
    orchestrator: MultiStepOrchestrator,
    mock_graph_query: MagicMock,
    mock_step_executor: MagicMock,
) -> None:
    query = MultiStepQuery(query="採購單的進貨單", account="2025shianyong")
    mock_graph_query.get_related_tables = AsyncMock(
        side_effect=[_gqr("採購單", ["進貨單"]), _gqr("進貨單", [])]
    )
    mock_step_executor.execute = AsyncMock(
        side_effect=[_make_step(0, "採購單"), _make_step(1, "進貨單")]
    )

    result = await orchestrator.execute(query)

    assert len(result.steps) == 2
    assert result.steps[0].table_name == "採購單"
    assert result.steps[1].table_name == "進貨單"
    assert result.partial_failure is False


@pytest.mark.asyncio
async def test_max_depth_limit(
    mock_graph_query: MagicMock,
    mock_step_executor: MagicMock,
    mock_result_merger: MagicMock,
) -> None:
    orch = MultiStepOrchestrator(
        graph_query=mock_graph_query,
        step_executor=mock_step_executor,
        result_merger=mock_result_merger,
    )
    query = MultiStepQuery(query="Deep chain", account="test", max_steps=3)
    mock_graph_query.get_related_tables = AsyncMock(
        side_effect=[_gqr("A", ["B"]), _gqr("B", ["C"]), _gqr("C", ["D"]), _gqr("D", ["E"])]
    )
    mock_step_executor.execute = AsyncMock(
        side_effect=[_make_step(0, "A"), _make_step(1, "B"), _make_step(2, "C")]
    )

    result = await orch.execute(query)

    assert len(result.steps) == 3
    assert result.partial_failure is True


@pytest.mark.asyncio
async def test_total_timeout(
    mock_graph_query: MagicMock,
    mock_step_executor: MagicMock,
    mock_result_merger: MagicMock,
) -> None:
    orch = MultiStepOrchestrator(
        graph_query=mock_graph_query,
        step_executor=mock_step_executor,
        result_merger=mock_result_merger,
    )
    query = MultiStepQuery(
        query="Slow query", account="test", total_timeout_s=1.0
    )
    mock_graph_query.get_related_tables = AsyncMock(return_value=_gqr("x", []))
    slow_exec = AsyncMock(side_effect=TimeoutError("Execution timeout"))
    mock_step_executor.execute = slow_exec

    result = await orch.execute(query)

    assert result.partial_failure is True
    assert len(result.errors) > 0


@pytest.mark.asyncio
async def test_step_timeout(
    mock_graph_query: MagicMock,
    mock_step_executor: MagicMock,
    mock_result_merger: MagicMock,
) -> None:
    orch = MultiStepOrchestrator(
        graph_query=mock_graph_query,
        step_executor=mock_step_executor,
        result_merger=mock_result_merger,
    )
    query = MultiStepQuery(query="Step timeout", account="test")
    mock_graph_query.get_related_tables = AsyncMock(side_effect=[_gqr("A", ["B"]), _gqr("B", [])])
    mock_step_executor.execute = AsyncMock(
        side_effect=[
            _make_step(0, "A"),
            _make_step(1, "B", error="Step timeout exceeded"),
        ]
    )

    result = await orch.execute(query)

    assert len(result.steps) == 2
    assert result.steps[0].error is None
    assert result.steps[1].error is not None
    assert result.partial_failure is True


@pytest.mark.asyncio
async def test_max_fan_out(
    mock_graph_query: MagicMock,
    mock_step_executor: MagicMock,
    mock_result_merger: MagicMock,
) -> None:
    orch = MultiStepOrchestrator(
        graph_query=mock_graph_query,
        step_executor=mock_step_executor,
        result_merger=mock_result_merger,
    )
    query = MultiStepQuery(
        query="Fan-out", account="test", max_fan_out=10
    )
    related = [f"Table_{i}" for i in range(15)]
    mock_graph_query.get_related_tables = AsyncMock(return_value=_gqr("T", related))
    mock_step_executor.execute = AsyncMock(return_value=_make_step(0, "T"))

    result = await orch.execute(query)

    assert mock_step_executor.execute.call_count <= 11


@pytest.mark.asyncio
async def test_cycle_detection(
    mock_graph_query: MagicMock,
    mock_step_executor: MagicMock,
    mock_result_merger: MagicMock,
) -> None:
    orch = MultiStepOrchestrator(
        graph_query=mock_graph_query,
        step_executor=mock_step_executor,
        result_merger=mock_result_merger,
    )
    query = MultiStepQuery(query="Circular", account="test")
    mock_graph_query.get_related_tables = AsyncMock(
        side_effect=[_gqr("A", ["B"]), _gqr("B", ["A"])]
    )
    mock_step_executor.execute = AsyncMock(
        side_effect=[_make_step(0, "A"), _make_step(1, "B")]
    )

    result = await orch.execute(query)

    assert len(result.steps) <= 2


@pytest.mark.asyncio
async def test_no_relations(
    orchestrator: MultiStepOrchestrator,
    mock_graph_query: MagicMock,
    mock_step_executor: MagicMock,
) -> None:
    query = MultiStepQuery(query="Isolated", account="test")
    mock_graph_query.get_related_tables = AsyncMock(return_value=_gqr("Orphan", []))
    mock_step_executor.execute = AsyncMock(return_value=_make_step(0, "Orphan"))

    result = await orchestrator.execute(query)

    assert len(result.steps) == 1
    assert result.steps[0].table_name == "Orphan"
    assert result.partial_failure is False


@pytest.mark.asyncio
async def test_partial_failure_metadata(
    orchestrator: MultiStepOrchestrator,
    mock_graph_query: MagicMock,
    mock_step_executor: MagicMock,
) -> None:
    query = MultiStepQuery(query="Partial fail", account="test")
    mock_graph_query.get_related_tables = AsyncMock(
        side_effect=[_gqr("A", ["B"]), _gqr("B", ["C"]), _gqr("C", [])]
    )
    mock_step_executor.execute = AsyncMock(
        side_effect=[
            _make_step(0, "A"),
            _make_step(1, "B", error="Query error"),
            _make_step(2, "C"),
        ]
    )

    result = await orchestrator.execute(query)

    assert len(result.steps) == 3
    assert result.partial_failure is True
    assert len(result.errors) == 1
    assert result.steps[0].error is None
    assert result.steps[1].error is not None
    assert result.steps[2].error is None
