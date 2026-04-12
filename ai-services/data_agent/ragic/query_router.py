"""
@file        query_router.py
@description Unified query routing for NL queries — Path A (tool-calling) vs fallback.
             Decides execution path based on ParseResult.query_type and confidence.
             Path A: simple_filter with high/medium confidence → tool_calling_engine.
             Fallback: returns original translated_params unchanged.
@lastUpdate  2026-04-13 02:14:43
@author      Daniel Chung
@version     1.0.0
"""

import logging

from data_agent.ragic.nl_parser import ParseResult
from data_agent.ragic.models import TranslatedParams
from data_agent.ragic.schema_linker import link_intent_to_schema
from data_agent.ragic.tool_calling_engine import (
    ToolCallingResult,
    tool_calling_generate,
)

logger = logging.getLogger(__name__)

_TOOL_CALLING_QUERY_TYPES = {"simple_filter"}


class RouteDecision:
    """Result of query routing with provenance info."""

    __slots__ = (
        "translated_params",
        "path_used",
        "tool_calling_result",
    )

    def __init__(
        self,
        translated_params: TranslatedParams,
        path_used: str = "fallback",
        tool_calling_result: ToolCallingResult | None = None,
    ) -> None:
        self.translated_params = translated_params
        self.path_used = path_used
        self.tool_calling_result = tool_calling_result


async def route_query_with_text(
    parsed: ParseResult,
    query: str,
) -> RouteDecision:
    """Route a parsed NL query to the appropriate execution path.

    Path A (tool-calling): simple_filter + high/medium confidence.
    Links intent to schema, builds JSON Schema enum, calls Ollama.
    Fallback: returns original translated_params unchanged.
    """
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


async def _execute_tool_calling(
    parsed: ParseResult,
    query: str,
) -> RouteDecision:
    """Schema link → tool-calling generation → validate."""
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
