"""
@file        query_router.py
@description Unified query routing for NL queries — Path A / Path B / fallback.
             Path A: simple_filter → tool_calling_engine (JSON Schema enum).
             Path B: aggregate/cross_table → aggregation_builder + pandas_engine.
             Fallback: returns original translated_params unchanged.
@lastUpdate  2026-04-13 02:46:54
@author      Daniel Chung
@version     2.0.0
"""

import logging

from data_agent.ragic.aggregation_builder import (
    AggregationResult,
    aggregation_generate,
    build_aggregation_schema,
)
from data_agent.ragic.models import TranslatedParams
from data_agent.ragic.nl_parser import ParseResult
from data_agent.ragic.pandas_engine import PandasEngineResult
from data_agent.ragic.schema_linker import link_intent_to_schema
from data_agent.ragic.tool_calling_engine import (
    ToolCallingResult,
    tool_calling_generate,
)

logger = logging.getLogger(__name__)

_TOOL_CALLING_QUERY_TYPES = {"simple_filter"}
_PANDAS_QUERY_TYPES = {"aggregate", "cross_table", "time_series"}


class RouteDecision:
    """Result of query routing with provenance info."""

    __slots__ = (
        "translated_params",
        "path_used",
        "tool_calling_result",
        "aggregation_result",
        "pandas_result",
    )

    def __init__(
        self,
        translated_params: TranslatedParams,
        path_used: str = "fallback",
        tool_calling_result: ToolCallingResult | None = None,
        aggregation_result: AggregationResult | None = None,
        pandas_result: PandasEngineResult | None = None,
    ) -> None:
        self.translated_params = translated_params
        self.path_used = path_used
        self.tool_calling_result = tool_calling_result
        self.aggregation_result = aggregation_result
        self.pandas_result = pandas_result


async def route_query_with_text(
    parsed: ParseResult,
    query: str,
) -> RouteDecision:
    """Route a parsed NL query to the appropriate execution path.

    Path B (pandas): aggregate/cross_table/time_series + table_key.
    Path A (tool-calling): simple_filter + high/medium confidence.
    Fallback: returns original translated_params unchanged.
    """
    if (
        parsed.query_type in _PANDAS_QUERY_TYPES
        and parsed.table_key
    ):
        return await _execute_pandas_path(parsed, query)

    if (
        parsed.query_type in _TOOL_CALLING_QUERY_TYPES
        and parsed.confidence in ("high", "medium")
        and parsed.table_key
    ):
        return await _execute_tool_calling(parsed, query)

    logger.debug(
        "Fallback path: query_type=%s confidence=%s",
        parsed.query_type,
        parsed.confidence,
    )
    return RouteDecision(
        translated_params=parsed.translated_params,
        path_used="fallback",
    )


async def _execute_pandas_path(
    parsed: ParseResult,
    query: str,
) -> RouteDecision:
    """Schema link → aggregation plan generation (Path B step 1).

    The actual pandas execution happens in router.py after receiving
    the RouteDecision, because it needs the RagicAPIClient instance.
    """
    linked = await link_intent_to_schema(parsed.table_key)
    if not linked.success:
        logger.warning(
            "Path B schema linking failed for %s: %s — falling back",
            parsed.table_key,
            linked.error_message,
        )
        return RouteDecision(
            translated_params=parsed.translated_params,
            path_used="fallback_schema_error",
        )

    agg_schema = build_aggregation_schema(linked.field_ids)

    agg_result = await aggregation_generate(
        query=query,
        agg_schema=agg_schema,
        field_label_map=linked.field_label_map,
    )

    if not agg_result.success or agg_result.plan is None:
        logger.warning(
            "Path B aggregation plan failed: %s — falling back",
            agg_result.error_message,
        )
        return RouteDecision(
            translated_params=parsed.translated_params,
            path_used="fallback_aggregation_error",
            aggregation_result=agg_result,
        )

    logger.info(
        "Path B plan ready: %d metrics, %d group_by, model=%s, %.0fms",
        len(agg_result.plan.metrics),
        len(agg_result.plan.group_by_fields),
        agg_result.model_used,
        agg_result.generation_time_ms,
    )

    return RouteDecision(
        translated_params=parsed.translated_params,
        path_used="pandas_engine",
        aggregation_result=agg_result,
    )


async def _execute_tool_calling(
    parsed: ParseResult,
    query: str,
) -> RouteDecision:
    """Schema link → tool-calling generation → validate (Path A)."""
    linked = await link_intent_to_schema(parsed.table_key)
    if not linked.success:
        logger.warning(
            "Schema linking failed for %s: %s — falling back",
            parsed.table_key,
            linked.error_message,
        )
        return RouteDecision(
            translated_params=parsed.translated_params,
            path_used="fallback_schema_error",
        )

    tc_result = await tool_calling_generate(
        query=query,
        tool_schema=linked.tool_schema,
        field_label_map=linked.field_label_map,
    )

    if tc_result.success and tc_result.translated_params.where:
        logger.info(
            "Path A success: %d filters, model=%s, %.0fms",
            len(tc_result.translated_params.where),
            tc_result.model_used,
            tc_result.generation_time_ms,
        )
        return RouteDecision(
            translated_params=tc_result.translated_params,
            path_used="tool_calling",
            tool_calling_result=tc_result,
        )

    logger.warning(
        "Path A tool-calling produced no filters — falling back. "
        "success=%s error=%s",
        tc_result.success,
        tc_result.error_message,
    )
    return RouteDecision(
        translated_params=parsed.translated_params,
        path_used="fallback_no_filters",
        tool_calling_result=tc_result,
    )
