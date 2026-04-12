"""
@file        aggregation_builder.py
@description Ollama JSON Schema constrained generation for aggregate queries.
             Produces an AggregationPlan (group_by, metrics, filters, order)
             from a natural language query, using enum constraint on field_ids.
@lastUpdate  2026-04-13 02:46:54
@author      Daniel Chung
@version     1.0.0
"""

import json
import logging
import os
import time

import httpx

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

_VALID_AGG_FUNCS = {"sum", "avg", "count", "min", "max"}
_VALID_OPERATORS = {"eq", "like", "gt", "gte", "lt", "lte"}


class AggregationPlan:
    """Structured aggregation plan produced by LLM."""

    __slots__ = (
        "group_by_fields",
        "metrics",
        "filters",
        "order_by",
        "order_direction",
        "limit",
    )

    def __init__(
        self,
        group_by_fields: list[str],
        metrics: list[dict[str, str]],
        filters: list[dict[str, str]],
        order_by: str | None = None,
        order_direction: str = "DESC",
        limit: int = 1000,
    ) -> None:
        self.group_by_fields = group_by_fields
        self.metrics = metrics
        self.filters = filters
        self.order_by = order_by
        self.order_direction = order_direction
        self.limit = limit


class AggregationResult:
    """Result of aggregation plan generation."""

    __slots__ = (
        "plan",
        "raw_response",
        "model_used",
        "generation_time_ms",
        "success",
        "error_message",
    )

    def __init__(
        self,
        plan: AggregationPlan | None = None,
        raw_response: str = "",
        model_used: str = "",
        generation_time_ms: float = 0.0,
        success: bool = True,
        error_message: str = "",
    ) -> None:
        self.plan = plan
        self.raw_response = raw_response
        self.model_used = model_used
        self.generation_time_ms = generation_time_ms
        self.success = success
        self.error_message = error_message


def build_aggregation_schema(
    field_ids: list[str],
) -> dict[str, object]:
    """Build JSON Schema for aggregation plan generation.

    Args:
        field_ids: Allowed field_id values (from ArangoDB schema).

    Returns:
        JSON Schema dict constraining LLM output.
    """
    ops = ["eq", "like", "gt", "gte", "lt", "lte"]
    agg_funcs = ["sum", "avg", "count", "min", "max"]
    schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "group_by": {
                "type": "array",
                "items": {"type": "string", "enum": field_ids},
            },
            "metrics": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "field_id": {"type": "string", "enum": field_ids},
                        "function": {"type": "string", "enum": agg_funcs},
                    },
                    "required": ["field_id", "function"],
                },
            },
            "filters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "field_id": {"type": "string", "enum": field_ids},
                        "operator": {"type": "string", "enum": ops},
                        "value": {"type": "string"},
                    },
                    "required": ["field_id", "operator", "value"],
                },
            },
            "order_by": {"type": "string", "enum": field_ids},
            "order_direction": {"type": "string", "enum": ["ASC", "DESC"]},
            "limit": {"type": "integer", "minimum": 1, "maximum": 5000},
        },
        "required": ["metrics"],
    }
    return schema


def _build_aggregation_prompt(
    query: str,
    field_label_map: dict[str, str],
) -> str:
    """Build prompt for aggregation plan generation."""
    field_lines = "\n".join(
        f"  {fid}: {name}" for fid, name in field_label_map.items()
    )
    return (
        "你是一個資料分析助手。根據使用者的自然語言查詢，產生聚合分析計畫。\n"
        "你只能使用以下欄位清單中的 field_id，嚴禁自行編造。\n\n"
        f"【欄位清單】\n{field_lines}\n\n"
        "【聚合函數說明】\n"
        "  sum: 加總\n"
        "  avg: 平均\n"
        "  count: 計數\n"
        "  min: 最小值\n"
        "  max: 最大值\n\n"
        "【運算子說明】\n"
        "  eq: 精確匹配\n"
        "  like: 模糊匹配（包含）\n"
        "  gt/gte/lt/lte: 大於/大於等於/小於/小於等於\n\n"
        "【日期格式】使用 YYYY/MM/DD 格式\n\n"
        f"【使用者查詢】{query}\n\n"
        "請輸出 JSON，包含 metrics 陣列（聚合指標）。\n"
        "若需要分組，加入 group_by 陣列。\n"
        "若有篩選條件，加入 filters 陣列。\n"
        "若需排序，加入 order_by 和 order_direction。"
    )


async def _get_llm_model() -> str:
    """Load LLM model name from system_params."""
    from data_agent.config_reader import get_param

    return await get_param("da.llm_model")


async def aggregation_generate(
    query: str,
    agg_schema: dict[str, object],
    field_label_map: dict[str, str],
    model: str | None = None,
) -> AggregationResult:
    """Call Ollama with JSON Schema constraint for aggregation plan.

    Args:
        query: User's natural language query.
        agg_schema: JSON Schema for the `format` parameter.
        field_label_map: field_id → Chinese label for prompt context.
        model: LLM model name override.

    Returns:
        AggregationResult with plan on success.
    """
    start = time.monotonic()
    llm_model = model or await _get_llm_model()
    prompt = _build_aggregation_prompt(query, field_label_map)

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": llm_model,
                    "prompt": prompt,
                    "format": agg_schema,
                    "stream": False,
                },
            )
            resp.raise_for_status()
    except httpx.TimeoutException:
        elapsed = (time.monotonic() - start) * 1000
        return AggregationResult(
            generation_time_ms=round(elapsed, 2),
            success=False,
            error_message="Ollama 呼叫逾時",
            model_used=llm_model,
        )
    except Exception as exc:
        elapsed = (time.monotonic() - start) * 1000
        return AggregationResult(
            generation_time_ms=round(elapsed, 2),
            success=False,
            error_message=f"Ollama 呼叫失敗：{exc}",
            model_used=llm_model,
        )

    raw_text = resp.json().get("response", "")
    elapsed = (time.monotonic() - start) * 1000

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        return AggregationResult(
            raw_response=raw_text,
            model_used=llm_model,
            generation_time_ms=round(elapsed, 2),
            success=False,
            error_message=f"JSON 解析失敗：{exc}",
        )

    valid_fids = set(field_label_map.keys())
    plan = _parse_aggregation_response(data, valid_fids)

    if not plan.metrics:
        return AggregationResult(
            plan=plan,
            raw_response=raw_text,
            model_used=llm_model,
            generation_time_ms=round(elapsed, 2),
            success=False,
            error_message="LLM 未產生有效的聚合指標",
        )

    return AggregationResult(
        plan=plan,
        raw_response=raw_text,
        model_used=llm_model,
        generation_time_ms=round(elapsed, 2),
        success=True,
    )


def _parse_aggregation_response(
    data: dict[str, object],
    valid_fids: set[str],
) -> AggregationPlan:
    """Parse and validate LLM JSON output into AggregationPlan."""
    group_by: list[str] = []
    raw_group = data.get("group_by", [])
    if isinstance(raw_group, list):
        for fid in raw_group:
            if isinstance(fid, str) and fid in valid_fids:
                group_by.append(fid)

    metrics: list[dict[str, str]] = []
    raw_metrics = data.get("metrics", [])
    if isinstance(raw_metrics, list):
        for m in raw_metrics:
            if not isinstance(m, dict):
                continue
            fid = str(m.get("field_id", ""))
            func = str(m.get("function", "")).lower()
            if fid in valid_fids and func in _VALID_AGG_FUNCS:
                metrics.append({"field_id": fid, "function": func})

    filters: list[dict[str, str]] = []
    raw_filters = data.get("filters", [])
    if isinstance(raw_filters, list):
        for f in raw_filters:
            if not isinstance(f, dict):
                continue
            fid = str(f.get("field_id", ""))
            op = str(f.get("operator", "eq")).lower()
            val = str(f.get("value", ""))
            if fid in valid_fids and val:
                if op not in _VALID_OPERATORS:
                    op = "eq"
                filters.append({"field_id": fid, "operator": op, "value": val})

    order_by = data.get("order_by")
    if not (isinstance(order_by, str) and order_by in valid_fids):
        order_by = None

    order_dir = "DESC"
    raw_dir = data.get("order_direction")
    if isinstance(raw_dir, str) and raw_dir.upper() in ("ASC", "DESC"):
        order_dir = raw_dir.upper()

    limit = 1000
    raw_limit = data.get("limit")
    if isinstance(raw_limit, int) and 1 <= raw_limit <= 5000:
        limit = raw_limit

    return AggregationPlan(
        group_by_fields=group_by,
        metrics=metrics,
        filters=filters,
        order_by=order_by if isinstance(order_by, str) else None,
        order_direction=order_dir,
        limit=limit,
    )
