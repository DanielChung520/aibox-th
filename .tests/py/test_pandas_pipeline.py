"""
@file        test_pandas_pipeline.py
@description Unit tests for Phase 3 Path B pipeline: aggregation_builder,
             pandas_engine, and query_router Path B routing.
@lastUpdate  2026-04-13 02:46:54
@author      Daniel Chung
@version     1.0.0
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from data_agent.ragic.aggregation_builder import (
    AggregationPlan,
    AggregationResult,
    _parse_aggregation_response,
    build_aggregation_schema,
)
from data_agent.ragic.models import RagicPagination, RagicQueryResult, RagicRecord
from data_agent.ragic.pandas_engine import (
    _apply_pre_filters,
    _execute_aggregation,
    records_to_dataframe,
)


# ── aggregation_builder tests ──


class TestBuildAggregationSchema:
    def test_schema_has_required_properties(self) -> None:
        schema: dict[str, Any] = build_aggregation_schema(["100", "200"])
        assert schema["type"] == "object"
        props = schema["properties"]
        assert isinstance(props, dict)
        assert "metrics" in props
        assert "group_by" in props
        assert "filters" in props

    def test_field_ids_in_enum(self) -> None:
        schema: dict[str, Any] = build_aggregation_schema(["f1", "f2", "f3"])
        props = schema["properties"]
        assert isinstance(props, dict)
        group_by = props["group_by"]
        assert isinstance(group_by, dict)
        items = group_by["items"]
        assert isinstance(items, dict)
        assert items["enum"] == ["f1", "f2", "f3"]

    def test_metrics_required(self) -> None:
        schema: dict[str, Any] = build_aggregation_schema(["100"])
        assert "metrics" in schema["required"]


class TestParseAggregationResponse:
    def test_valid_metrics(self) -> None:
        data: dict[str, Any] = {
            "metrics": [
                {"field_id": "100", "function": "sum"},
                {"field_id": "200", "function": "avg"},
            ],
            "group_by": ["100"],
        }
        plan = _parse_aggregation_response(data, {"100", "200"})
        assert len(plan.metrics) == 2
        assert plan.metrics[0]["function"] == "sum"
        assert plan.group_by_fields == ["100"]

    def test_invalid_field_id_dropped(self) -> None:
        data: dict[str, Any] = {
            "metrics": [{"field_id": "999", "function": "sum"}],
        }
        plan = _parse_aggregation_response(data, {"100"})
        assert len(plan.metrics) == 0

    def test_invalid_function_dropped(self) -> None:
        data: dict[str, Any] = {
            "metrics": [{"field_id": "100", "function": "median"}],
        }
        plan = _parse_aggregation_response(data, {"100"})
        assert len(plan.metrics) == 0

    def test_filters_parsed(self) -> None:
        data: dict[str, Any] = {
            "metrics": [{"field_id": "100", "function": "sum"}],
            "filters": [
                {"field_id": "200", "operator": "gte", "value": "2026/03/01"},
            ],
        }
        plan = _parse_aggregation_response(data, {"100", "200"})
        assert len(plan.filters) == 1
        assert plan.filters[0]["operator"] == "gte"

    def test_invalid_operator_defaults_eq(self) -> None:
        data: dict[str, Any] = {
            "metrics": [{"field_id": "100", "function": "count"}],
            "filters": [
                {"field_id": "100", "operator": "invalid_op", "value": "abc"},
            ],
        }
        plan = _parse_aggregation_response(data, {"100"})
        assert plan.filters[0]["operator"] == "eq"

    def test_order_and_limit(self) -> None:
        data: dict[str, Any] = {
            "metrics": [{"field_id": "100", "function": "sum"}],
            "order_by": "100",
            "order_direction": "ASC",
            "limit": 50,
        }
        plan = _parse_aggregation_response(data, {"100"})
        assert plan.order_by == "100"
        assert plan.order_direction == "ASC"
        assert plan.limit == 50


# ── pandas_engine tests ──


def _make_query_result(rows: list[dict[str, object]]) -> RagicQueryResult:
    records = [
        RagicRecord(ragic_id=str(i), fields=row) for i, row in enumerate(rows)
    ]
    return RagicQueryResult(
        records=records,
        record_count=len(records),
        pagination=RagicPagination(
            offset=0, limit=len(records), returned_count=len(records)
        ),
    )


class TestRecordsToDataframe:
    def test_basic_conversion(self) -> None:
        qr = _make_query_result([
            {"100": "apple", "200": "10"},
            {"100": "banana", "200": "20"},
        ])
        df = records_to_dataframe(qr)
        assert len(df) == 2
        assert "100" in df.columns
        assert "_ragic_id" in df.columns

    def test_rename_columns(self) -> None:
        qr = _make_query_result([{"100": "val"}])
        df = records_to_dataframe(qr, field_label_map={"100": "品名"})
        assert "品名" in df.columns
        assert "100" not in df.columns

    def test_empty_records(self) -> None:
        qr = _make_query_result([])
        df = records_to_dataframe(qr)
        assert df.empty


class TestApplyPreFilters:
    def test_eq_filter(self) -> None:
        df = pd.DataFrame({"品名": ["apple", "banana", "cherry"]})
        result = _apply_pre_filters(
            df,
            [{"field_id": "100", "operator": "eq", "value": "banana"}],
            {"100": "品名"},
        )
        assert len(result) == 1
        assert result.iloc[0]["品名"] == "banana"

    def test_like_filter(self) -> None:
        df = pd.DataFrame({"品名": ["apple pie", "banana", "cherry"]})
        result = _apply_pre_filters(
            df,
            [{"field_id": "100", "operator": "like", "value": "apple"}],
            {"100": "品名"},
        )
        assert len(result) == 1

    def test_numeric_gte_filter(self) -> None:
        df = pd.DataFrame({"金額": ["100", "200", "300"]})
        result = _apply_pre_filters(
            df,
            [{"field_id": "200", "operator": "gte", "value": "200"}],
            {"200": "金額"},
        )
        assert len(result) == 2

    def test_nonexistent_column_ignored(self) -> None:
        df = pd.DataFrame({"品名": ["apple"]})
        result = _apply_pre_filters(
            df,
            [{"field_id": "999", "operator": "eq", "value": "x"}],
            {"999": "不存在的欄位"},
        )
        assert len(result) == 1


class TestExecuteAggregation:
    def test_sum_with_group_by(self) -> None:
        df = pd.DataFrame({
            "供應商": ["A", "A", "B"],
            "金額": ["100", "200", "300"],
        })
        plan = AggregationPlan(
            group_by_fields=["f1"],
            metrics=[{"field_id": "f2", "function": "sum"}],
            filters=[],
        )
        result = _execute_aggregation(df, plan, {"f1": "供應商", "f2": "金額"})
        assert len(result) == 2
        row_a = result[result["供應商"] == "A"]
        assert float(row_a["金額_sum"].iloc[0]) == 300.0

    def test_count_without_group_by(self) -> None:
        df = pd.DataFrame({"金額": ["100", "200", "300"]})
        plan = AggregationPlan(
            group_by_fields=[],
            metrics=[{"field_id": "f1", "function": "count"}],
            filters=[],
        )
        result = _execute_aggregation(df, plan, {"f1": "金額"})
        assert len(result) == 1
        assert int(result["金額_count"].iloc[0]) == 3

    def test_avg_aggregation(self) -> None:
        df = pd.DataFrame({"金額": ["10", "20", "30"]})
        plan = AggregationPlan(
            group_by_fields=[],
            metrics=[{"field_id": "f1", "function": "avg"}],
            filters=[],
        )
        result = _execute_aggregation(df, plan, {"f1": "金額"})
        assert float(result["金額_avg"].iloc[0]) == 20.0

    def test_nonexistent_metric_column(self) -> None:
        df = pd.DataFrame({"品名": ["apple"]})
        plan = AggregationPlan(
            group_by_fields=[],
            metrics=[{"field_id": "f1", "function": "sum"}],
            filters=[],
        )
        result = _execute_aggregation(df, plan, {"f1": "不存在"})
        assert result.empty


# ── query_router Path B tests ──


class TestQueryRouterPathB:
    @pytest.mark.asyncio
    async def test_aggregate_routes_to_pandas(self) -> None:
        from data_agent.ragic.query_router import route_query_with_text

        parsed = MagicMock()
        parsed.query_type = "aggregate"
        parsed.table_key = "ERP_13/10"
        parsed.confidence = "high"
        parsed.translated_params = MagicMock()

        mock_linked = MagicMock()
        mock_linked.success = True
        mock_linked.field_ids = ["100", "200"]
        mock_linked.field_label_map = {"100": "供應商", "200": "金額"}

        mock_agg = AggregationResult(
            plan=AggregationPlan(
                group_by_fields=["100"],
                metrics=[{"field_id": "200", "function": "sum"}],
                filters=[],
            ),
            success=True,
            model_used="test-model",
            generation_time_ms=100.0,
        )

        with (
            patch(
                "data_agent.ragic.query_router.link_intent_to_schema",
                new_callable=AsyncMock,
                return_value=mock_linked,
            ),
            patch(
                "data_agent.ragic.query_router.aggregation_generate",
                new_callable=AsyncMock,
                return_value=mock_agg,
            ),
        ):
            decision = await route_query_with_text(parsed, "三月各供應商進貨總額")
            assert decision.path_used == "pandas_engine"
            assert decision.aggregation_result is not None
            assert decision.aggregation_result.plan is not None

    @pytest.mark.asyncio
    async def test_aggregate_schema_failure_fallback(self) -> None:
        from data_agent.ragic.query_router import route_query_with_text

        parsed = MagicMock()
        parsed.query_type = "aggregate"
        parsed.table_key = "ERP_13/10"
        parsed.confidence = "high"
        parsed.translated_params = MagicMock()

        mock_linked = MagicMock()
        mock_linked.success = False
        mock_linked.error_message = "table not found"

        with patch(
            "data_agent.ragic.query_router.link_intent_to_schema",
            new_callable=AsyncMock,
            return_value=mock_linked,
        ):
            decision = await route_query_with_text(parsed, "test query")
            assert decision.path_used == "fallback_schema_error"

    @pytest.mark.asyncio
    async def test_simple_filter_still_routes_to_path_a(self) -> None:
        from data_agent.ragic.query_router import route_query_with_text

        parsed = MagicMock()
        parsed.query_type = "simple_filter"
        parsed.table_key = "ERP_13/10"
        parsed.confidence = "high"
        parsed.translated_params = MagicMock()

        mock_linked = MagicMock()
        mock_linked.success = True
        mock_linked.tool_schema = {"type": "object"}
        mock_linked.field_label_map = {"100": "品名"}

        mock_tc = MagicMock()
        mock_tc.success = True
        mock_tc.translated_params = MagicMock()
        mock_tc.translated_params.where = [MagicMock()]
        mock_tc.model_used = "test"
        mock_tc.generation_time_ms = 50.0

        with (
            patch(
                "data_agent.ragic.query_router.link_intent_to_schema",
                new_callable=AsyncMock,
                return_value=mock_linked,
            ),
            patch(
                "data_agent.ragic.query_router.tool_calling_generate",
                new_callable=AsyncMock,
                return_value=mock_tc,
            ),
        ):
            decision = await route_query_with_text(parsed, "查詢供應商為ABC")
            assert decision.path_used == "tool_calling"

    @pytest.mark.asyncio
    async def test_low_confidence_fallback(self) -> None:
        from data_agent.ragic.query_router import route_query_with_text

        parsed = MagicMock()
        parsed.query_type = "aggregate"
        parsed.table_key = ""
        parsed.confidence = "low"
        parsed.translated_params = MagicMock()

        decision = await route_query_with_text(parsed, "test")
        assert decision.path_used == "fallback"
