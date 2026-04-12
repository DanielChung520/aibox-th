"""
@file        test_tool_calling_pipeline.py
@description Unit tests for Phase 2 Path A pipeline: tool_calling_engine,
             schema_linker, query_router. All external calls (Ollama, ArangoDB)
             are mocked.
@lastUpdate  2026-04-13 02:14:43
@author      Daniel Chung
@version     1.0.0
"""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from data_agent.ragic.models import (
    MatchedIntentInfo,
    RagicOperator,
    TranslatedParams,
)
from data_agent.ragic.nl_parser import ParseResult
from data_agent.ragic.query_router import route_query_with_text
from data_agent.ragic.schema_linker import LinkedSchema, link_intent_to_schema
from data_agent.ragic.tool_calling_engine import (
    ToolCallingResult,
    _parse_tool_response,
    build_tool_schema,
    tool_calling_generate,
)


SAMPLE_FIELD_IDS = ["1023120", "1023123", "1023122", "1023148"]
SAMPLE_FIELD_LABELS = {
    "1023120": "進貨單號",
    "1023123": "日期",
    "1023122": "供應商名稱",
    "1023148": "含稅總計",
}


class TestBuildToolSchema:
    def test_builds_valid_schema(self) -> None:
        schema: dict[str, Any] = build_tool_schema(SAMPLE_FIELD_IDS)
        assert schema["type"] == "object"
        assert "filters" in schema["properties"]
        filters_prop = schema["properties"]["filters"]
        items = filters_prop["items"]
        field_id_prop = items["properties"]["field_id"]
        assert field_id_prop["enum"] == SAMPLE_FIELD_IDS

    def test_enum_constrains_field_ids(self) -> None:
        schema: dict[str, Any] = build_tool_schema(["100", "200"])
        items = schema["properties"]["filters"]["items"]
        assert items["properties"]["field_id"]["enum"] == ["100", "200"]

    def test_custom_operators(self) -> None:
        schema: dict[str, Any] = build_tool_schema(["100"], operators=["eq", "like"])
        items = schema["properties"]["filters"]["items"]
        assert items["properties"]["operator"]["enum"] == ["eq", "like"]


class TestParseToolResponse:
    def test_valid_filters(self) -> None:
        data: dict[str, object] = {
            "filters": [
                {"field_id": "1023123", "operator": "gte", "value": "2026/03/01"},
                {"field_id": "1023122", "operator": "like", "value": "台灣"},
            ]
        }
        result = _parse_tool_response(data, set(SAMPLE_FIELD_IDS))
        assert len(result.where) == 2
        assert result.where[0].field_id == "1023123"
        assert result.where[0].operator == RagicOperator.GTE
        assert result.where[1].value == "台灣"

    def test_invalid_field_id_dropped(self) -> None:
        data: dict[str, object] = {
            "filters": [
                {"field_id": "9999999", "operator": "eq", "value": "test"},
            ]
        }
        result = _parse_tool_response(data, set(SAMPLE_FIELD_IDS))
        assert len(result.where) == 0

    def test_invalid_operator_defaults_eq(self) -> None:
        data: dict[str, object] = {
            "filters": [
                {"field_id": "1023120", "operator": "INVALID", "value": "test"},
            ]
        }
        result = _parse_tool_response(data, set(SAMPLE_FIELD_IDS))
        assert len(result.where) == 1
        assert result.where[0].operator == RagicOperator.EQ

    def test_order_field_valid(self) -> None:
        data: dict[str, object] = {
            "filters": [],
            "order_field": "1023123",
            "order_direction": "ASC",
        }
        result = _parse_tool_response(data, set(SAMPLE_FIELD_IDS))
        assert result.order_field == "1023123"
        assert result.order_direction == "ASC"

    def test_order_field_invalid_dropped(self) -> None:
        data: dict[str, object] = {
            "filters": [],
            "order_field": "9999999",
        }
        result = _parse_tool_response(data, set(SAMPLE_FIELD_IDS))
        assert result.order_field is None

    def test_limit_within_range(self) -> None:
        data: dict[str, object] = {"filters": [], "limit": 50}
        result = _parse_tool_response(data, set(SAMPLE_FIELD_IDS))
        assert result.limit == 50

    def test_limit_out_of_range_defaults(self) -> None:
        data: dict[str, object] = {"filters": [], "limit": 99999}
        result = _parse_tool_response(data, set(SAMPLE_FIELD_IDS))
        assert result.limit == 1000

    def test_empty_value_dropped(self) -> None:
        data: dict[str, object] = {
            "filters": [
                {"field_id": "1023120", "operator": "eq", "value": ""},
            ]
        }
        result = _parse_tool_response(data, set(SAMPLE_FIELD_IDS))
        assert len(result.where) == 0


class TestToolCallingGenerate:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        mock_response = {
            "response": json.dumps({
                "filters": [
                    {"field_id": "1023122", "operator": "like", "value": "大成"}
                ]
            })
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status = MagicMock()

        with patch("data_agent.ragic.tool_calling_engine._get_llm_model", return_value="qwen3:8b"):
            with patch("data_agent.ragic.tool_calling_engine.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.post.return_value = mock_resp
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                result = await tool_calling_generate(
                    query="查大成的進貨單",
                    tool_schema=build_tool_schema(SAMPLE_FIELD_IDS),
                    field_label_map=SAMPLE_FIELD_LABELS,
                )

        assert result.success
        assert len(result.translated_params.where) == 1
        assert result.translated_params.where[0].value == "大成"

    @pytest.mark.asyncio
    async def test_timeout_returns_failure(self) -> None:
        import httpx as httpx_mod

        with patch("data_agent.ragic.tool_calling_engine._get_llm_model", return_value="qwen3:8b"):
            with patch("data_agent.ragic.tool_calling_engine.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.post.side_effect = httpx_mod.TimeoutException("timeout")
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                result = await tool_calling_generate(
                    query="test",
                    tool_schema=build_tool_schema(SAMPLE_FIELD_IDS),
                    field_label_map=SAMPLE_FIELD_LABELS,
                )

        assert not result.success
        assert "逾時" in result.error_message


class TestSchemaLinker:
    @pytest.mark.asyncio
    async def test_empty_table_key(self) -> None:
        result = await link_intent_to_schema("")
        assert not result.success
        assert "為空" in result.error_message

    @pytest.mark.asyncio
    async def test_success_with_mock(self) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "result": [
                {"field_id": "1023120", "field_name": "進貨單號", "field_type": "VARCHAR"},
                {"field_id": "1023123", "field_name": "日期", "field_type": "DATE"},
            ]
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("data_agent.ragic.schema_linker.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await link_intent_to_schema("erp/48")

        assert result.success
        assert result.field_count == 2
        assert "1023120" in result.field_label_map
        assert result.field_label_map["1023123"] == "日期"
        assert len(result.tool_schema) > 0


class TestQueryRouter:
    def _make_parse_result(
        self,
        confidence: str = "high",
        query_type: str = "simple_filter",
        table_key: str = "erp/48",
    ) -> ParseResult:
        return ParseResult(
            intent_matched=MatchedIntentInfo(
                intent_id="intent_erp48_list",
                score=0.85,
                action="list",
                table_key=table_key,
            ),
            translated_params=TranslatedParams(),
            table_key=table_key,
            parse_time_ms=10.0,
            confidence=confidence,
            query_type=query_type,
        )

    @pytest.mark.asyncio
    async def test_fallback_on_low_confidence(self) -> None:
        parsed = self._make_parse_result(confidence="low")
        decision = await route_query_with_text(parsed, "test query")
        assert decision.path_used == "fallback"

    @pytest.mark.asyncio
    async def test_fallback_on_aggregate_type(self) -> None:
        parsed = self._make_parse_result(query_type="aggregate")
        decision = await route_query_with_text(parsed, "test query")
        assert decision.path_used == "fallback"

    @pytest.mark.asyncio
    async def test_path_a_routes_to_tool_calling(self) -> None:
        linked = LinkedSchema(
            tool_schema=build_tool_schema(SAMPLE_FIELD_IDS),
            field_label_map=SAMPLE_FIELD_LABELS,
            field_ids=SAMPLE_FIELD_IDS,
            table_key="erp/48",
        )
        tc_result = ToolCallingResult(
            translated_params=TranslatedParams(
                where=[],
                limit=1000,
            ),
            success=True,
        )

        with patch("data_agent.ragic.query_router.link_intent_to_schema", return_value=linked):
            with patch("data_agent.ragic.query_router.tool_calling_generate", return_value=tc_result):
                parsed = self._make_parse_result()
                decision = await route_query_with_text(parsed, "查大成進貨單")

        # tc_result has no where clauses → fallback
        assert decision.path_used == "fallback_no_filters"

    @pytest.mark.asyncio
    async def test_path_a_success_with_filters(self) -> None:
        from data_agent.ragic.models import RagicWhereClause

        linked = LinkedSchema(
            tool_schema=build_tool_schema(SAMPLE_FIELD_IDS),
            field_label_map=SAMPLE_FIELD_LABELS,
            field_ids=SAMPLE_FIELD_IDS,
            table_key="erp/48",
        )
        tc_result = ToolCallingResult(
            translated_params=TranslatedParams(
                where=[
                    RagicWhereClause(field_id="1023122", operator=RagicOperator.LIKE, value="大成"),
                ],
            ),
            success=True,
        )

        with patch("data_agent.ragic.query_router.link_intent_to_schema", return_value=linked):
            with patch("data_agent.ragic.query_router.tool_calling_generate", return_value=tc_result):
                parsed = self._make_parse_result()
                decision = await route_query_with_text(parsed, "查大成進貨單")

        assert decision.path_used == "tool_calling"
        assert len(decision.translated_params.where) == 1
        assert decision.translated_params.where[0].value == "大成"

    @pytest.mark.asyncio
    async def test_schema_link_failure_fallback(self) -> None:
        failed_linked = LinkedSchema(
            tool_schema={},
            field_label_map={},
            field_ids=[],
            success=False,
            error_message="ArangoDB down",
        )

        with patch("data_agent.ragic.query_router.link_intent_to_schema", return_value=failed_linked):
            parsed = self._make_parse_result()
            decision = await route_query_with_text(parsed, "查進貨單")

        assert decision.path_used == "fallback_schema_error"
