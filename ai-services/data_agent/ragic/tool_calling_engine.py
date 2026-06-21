"""
@file        tool_calling_engine.py
@description Ollama JSON Schema constrained generation for NL→filter translation.
             Uses `format` parameter to force LLM output into a strict schema
             where field_id values are constrained by enum — preventing hallucination.
             This replaces the free-form LLM fallback for simple_filter queries.
@lastUpdate  2026-04-13 02:14:43
@author      Daniel Chung
@version     1.0.0
"""

import json
import logging
import os
import time

import httpx

from data_agent.ragic.models import (
    RagicOperator,
    RagicWhereClause,
    TranslatedParams,
)

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("MLX_BASE_URL", os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11400"))

_VALID_OPERATORS = {"eq", "like", "gt", "gte", "lt", "lte"}


class ToolCallingResult:
    """Result of a tool-calling constrained LLM generation."""

    __slots__ = (
        "translated_params",
        "raw_response",
        "model_used",
        "generation_time_ms",
        "success",
        "error_message",
    )

    def __init__(
        self,
        translated_params: TranslatedParams,
        raw_response: str = "",
        model_used: str = "",
        generation_time_ms: float = 0.0,
        success: bool = True,
        error_message: str = "",
    ) -> None:
        self.translated_params = translated_params
        self.raw_response = raw_response
        self.model_used = model_used
        self.generation_time_ms = generation_time_ms
        self.success = success
        self.error_message = error_message


async def _get_llm_model() -> str:
    """Load LLM model name from system_params."""
    from data_agent.config_reader import get_param

    return await get_param("da.llm_model")


def build_tool_schema(
    field_ids: list[str],
    operators: list[str] | None = None,
) -> dict[str, object]:
    """Build JSON Schema for Ollama `format` parameter.

    Args:
        field_ids: Allowed field_id values (from ArangoDB schema).
        operators: Allowed operator values. Defaults to standard set.

    Returns:
        JSON Schema dict constraining LLM output to valid field_ids only.
    """
    ops = operators or ["eq", "like", "gt", "gte", "lt", "lte"]
    schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "filters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "field_id": {
                            "type": "string",
                            "enum": field_ids,
                        },
                        "operator": {
                            "type": "string",
                            "enum": ops,
                        },
                        "value": {"type": "string"},
                    },
                    "required": ["field_id", "operator", "value"],
                },
            },
            "order_field": {
                "type": "string",
                "enum": field_ids,
            },
            "order_direction": {
                "type": "string",
                "enum": ["ASC", "DESC"],
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 5000,
            },
        },
        "required": ["filters"],
    }
    return schema


def _build_prompt(
    query: str,
    field_label_map: dict[str, str],
) -> str:
    """Build system + user prompt for constrained generation.

    Args:
        query: User's natural language query.
        field_label_map: Mapping of field_id → Chinese field name.

    Returns:
        Prompt string for Ollama.
    """
    field_lines = "\n".join(
        f"  {fid}: {name}" for fid, name in field_label_map.items()
    )
    return (
        "你是一個資料查詢助手。根據使用者的自然語言查詢，產生篩選條件。\n"
        "你只能使用以下欄位清單中的 field_id，嚴禁自行編造。\n\n"
        f"【欄位清單】\n{field_lines}\n\n"
        "【運算子說明】\n"
        "  eq: 精確匹配\n"
        "  like: 模糊匹配（包含）\n"
        "  gt/gte/lt/lte: 數值或日期的大於/大於等於/小於/小於等於\n\n"
        "【日期格式】使用 YYYY/MM/DD 格式\n\n"
        f"【使用者查詢】{query}\n\n"
        "請輸出 JSON，包含 filters 陣列。"
        "若需排序，加入 order_field 和 order_direction。"
        "若使用者指定筆數，加入 limit。"
    )


async def tool_calling_generate(
    query: str,
    tool_schema: dict[str, object],
    field_label_map: dict[str, str],
    model: str | None = None,
) -> ToolCallingResult:
    """Call Ollama with JSON Schema constraint to produce structured filters.

    Args:
        query: User's natural language query.
        tool_schema: JSON Schema for the `format` parameter.
        field_label_map: field_id → Chinese label for prompt context.
        model: LLM model name. If None, loaded from system_params.

    Returns:
        ToolCallingResult with translated_params on success.
    """
    start = time.monotonic()
    llm_model = model or await _get_llm_model()
    prompt = _build_prompt(query, field_label_map)

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/v1/chat/completions",
                json={
                    "model": llm_model,
                    "prompt": prompt,
                    "format": tool_schema,
                    "stream": False,
                },
            )
            resp.raise_for_status()
    except httpx.TimeoutException:
        elapsed = (time.monotonic() - start) * 1000
        return ToolCallingResult(
            translated_params=TranslatedParams(),
            generation_time_ms=round(elapsed, 2),
            success=False,
            error_message="Ollama 呼叫逾時",
            model_used=llm_model,
        )
    except Exception as exc:
        elapsed = (time.monotonic() - start) * 1000
        return ToolCallingResult(
            translated_params=TranslatedParams(),
            generation_time_ms=round(elapsed, 2),
            success=False,
            error_message=f"Ollama 呼叫失敗：{exc}",
            model_used=llm_model,
        )

    raw_text = resp.json().get("choices",[{}])[0].get("message",{}).get("content","")
    elapsed = (time.monotonic() - start) * 1000

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        return ToolCallingResult(
            translated_params=TranslatedParams(),
            raw_response=raw_text,
            model_used=llm_model,
            generation_time_ms=round(elapsed, 2),
            success=False,
            error_message=f"JSON 解析失敗：{exc}",
        )

    valid_fids = set(field_label_map.keys())
    params = _parse_tool_response(data, valid_fids)

    return ToolCallingResult(
        translated_params=params,
        raw_response=raw_text,
        model_used=llm_model,
        generation_time_ms=round(elapsed, 2),
        success=True,
    )


def _parse_tool_response(
    data: dict[str, object],
    valid_fids: set[str],
) -> TranslatedParams:
    """Parse and validate LLM JSON output into TranslatedParams.

    Even with schema constraint, we still validate field_ids as a safety net.

    Args:
        data: Parsed JSON dict from LLM.
        valid_fids: Set of allowed field_id values.

    Returns:
        Validated TranslatedParams.
    """
    where_clauses: list[RagicWhereClause] = []
    raw_filters = data.get("filters", [])
    if isinstance(raw_filters, list):
        for f in raw_filters:
            if not isinstance(f, dict):
                continue
            fid = str(f.get("field_id", ""))
            op_raw = str(f.get("operator", "eq")).lower()
            val = str(f.get("value", ""))
            if not fid or not val:
                continue
            if fid not in valid_fids:
                logger.warning("Tool-calling produced invalid field_id %s — dropped", fid)
                continue
            if op_raw not in _VALID_OPERATORS:
                op_raw = "eq"
            where_clauses.append(
                RagicWhereClause(
                    field_id=fid,
                    operator=RagicOperator(op_raw),
                    value=val,
                )
            )

    order_field = data.get("order_field")
    if isinstance(order_field, str) and order_field in valid_fids:
        pass
    else:
        order_field = None

    order_dir_raw = data.get("order_direction")
    order_dir = "DESC"
    if isinstance(order_dir_raw, str) and order_dir_raw.upper() in ("ASC", "DESC"):
        order_dir = order_dir_raw.upper()

    limit_raw = data.get("limit")
    limit = 1000
    if isinstance(limit_raw, int) and 1 <= limit_raw <= 5000:
        limit = limit_raw

    return TranslatedParams(
        where=where_clauses,
        limit=limit,
        naming="EID",
        order_field=order_field if isinstance(order_field, str) else None,
        order_direction=order_dir,
    )
