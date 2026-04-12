"""
@file        pandas_engine.py
@description Pandas-based local aggregation engine for Path B queries.
             Fetches full table data via Ragic API, converts to DataFrame,
             applies filters, groupby, and aggregation using pandas operations.
@lastUpdate  2026-04-13 02:56:46
@author      Daniel Chung
@version     1.0.0
"""

from __future__ import annotations

import logging
import time

import pandas as pd

from data_agent.ragic.aggregation_builder import AggregationPlan
from data_agent.ragic.client import RagicAPIClient
from data_agent.ragic.models import RagicQueryResult, RagicWhereClause

logger = logging.getLogger(__name__)

_OPERATOR_MAP = {
    "eq": "==",
    "like": "str.contains",
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
}

_PANDAS_AGG_MAP: dict[str, str] = {
    "avg": "mean",
    "sum": "sum",
    "count": "count",
    "min": "min",
    "max": "max",
}


class PandasEngineResult:
    """Result of a pandas aggregation execution."""

    __slots__ = (
        "data",
        "columns",
        "row_count",
        "group_by_fields",
        "metrics_applied",
        "execution_time_ms",
        "source_record_count",
        "success",
        "error_message",
    )

    def __init__(
        self,
        data: list[dict[str, object]] | None = None,
        columns: list[str] | None = None,
        row_count: int = 0,
        group_by_fields: list[str] | None = None,
        metrics_applied: list[dict[str, str]] | None = None,
        execution_time_ms: float = 0.0,
        source_record_count: int = 0,
        success: bool = True,
        error_message: str = "",
    ) -> None:
        self.data = data or []
        self.columns = columns or []
        self.row_count = row_count
        self.group_by_fields = group_by_fields or []
        self.metrics_applied = metrics_applied or []
        self.execution_time_ms = execution_time_ms
        self.source_record_count = source_record_count
        self.success = success
        self.error_message = error_message


def records_to_dataframe(
    query_result: RagicQueryResult,
    field_label_map: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Convert RagicQueryResult records to a pandas DataFrame.

    Each record's fields dict is flattened into a row.
    Nested dicts (subtables) and lists are kept as-is.
    If field_label_map is provided, columns are renamed to human-readable names.
    """
    rows: list[dict[str, object]] = []
    for rec in query_result.records:
        row: dict[str, object] = dict(rec.fields)
        row["_ragic_id"] = rec.ragic_id
        rows.append(row)

    df = pd.DataFrame(rows)

    if field_label_map and not df.empty:
        rename_map = {
            fid: label for fid, label in field_label_map.items() if fid in df.columns
        }
        df = df.rename(columns=rename_map)

    return df


def _apply_pre_filters(
    df: pd.DataFrame,
    filters: list[dict[str, str]],
    field_label_map: dict[str, str],
) -> pd.DataFrame:
    """Apply WHERE-like filters to DataFrame before aggregation."""
    if df.empty or not filters:
        return df

    for f in filters:
        fid = f.get("field_id", "")
        op = f.get("operator", "eq")
        val = f.get("value", "")
        col = field_label_map.get(fid, fid)

        if col not in df.columns:
            continue

        series = df[col]
        numeric = pd.to_numeric(series, errors="coerce")
        has_numeric = numeric.notna().any()

        if op == "like":
            df = df[series.astype(str).str.contains(val, case=False, na=False)]
        elif op == "eq":
            if has_numeric:
                try:
                    df = df[numeric == float(val)]
                except (ValueError, TypeError):
                    df = df[series.astype(str) == val]
            else:
                df = df[series.astype(str) == val]
        elif op in ("gt", "gte", "lt", "lte") and has_numeric:
            try:
                num_val = float(val)
            except (ValueError, TypeError):
                continue
            if op == "gt":
                df = df[numeric > num_val]
            elif op == "gte":
                df = df[numeric >= num_val]
            elif op == "lt":
                df = df[numeric < num_val]
            elif op == "lte":
                df = df[numeric <= num_val]

    return df


def _resolve_original_label(
    col: str,
    pandas_func: str,
    plan: AggregationPlan,
    field_label_map: dict[str, str],
) -> str:
    """Resolve the original user-facing function name for column naming.

    For example, maps pandas 'mean' back to user-facing 'avg'.
    """
    for m in plan.metrics:
        mapped_col = field_label_map.get(m["field_id"], m["field_id"])
        mapped_func = _PANDAS_AGG_MAP.get(m["function"], m["function"])
        if mapped_col == col and mapped_func == pandas_func:
            return m["function"]
    return pandas_func


def _execute_aggregation(
    df: pd.DataFrame,
    plan: AggregationPlan,
    field_label_map: dict[str, str],
) -> pd.DataFrame:
    """Execute groupby + aggregation on DataFrame."""
    group_cols = [field_label_map.get(fid, fid) for fid in plan.group_by_fields]
    valid_group_cols = [c for c in group_cols if c in df.columns]

    agg_spec: dict[str, list[str]] = {}
    for metric in plan.metrics:
        col = field_label_map.get(metric["field_id"], metric["field_id"])
        if col not in df.columns:
            continue
        df[col] = pd.to_numeric(df[col], errors="coerce")
        pandas_func = _PANDAS_AGG_MAP.get(metric["function"], metric["function"])
        agg_spec.setdefault(col, []).append(pandas_func)

    if not agg_spec:
        return pd.DataFrame()

    if valid_group_cols:
        result = df.groupby(valid_group_cols, dropna=False).agg(agg_spec)
        result.columns = [
            f"{col}_{_resolve_original_label(col, func, plan, field_label_map)}"
            for col, funcs in agg_spec.items()
            for func in funcs
        ]
        result = result.reset_index()
    else:
        agg_result: dict[str, object] = {}
        for col, funcs in agg_spec.items():
            for func in funcs:
                label = _resolve_original_label(
                    col, func, plan, field_label_map,
                )
                agg_result[f"{col}_{label}"] = getattr(df[col], func)()
        result = pd.DataFrame([agg_result])

    return result


async def fetch_and_aggregate(
    client: RagicAPIClient,
    tab_path: str,
    sheet_index: int,
    plan: AggregationPlan,
    field_label_map: dict[str, str],
    pre_filters: list[RagicWhereClause] | None = None,
) -> PandasEngineResult:
    """Full Path B pipeline: fetch → DataFrame → filter → aggregate.

    Args:
        client: Configured RagicAPIClient instance.
        tab_path: Ragic tab path (e.g. "ERP_13").
        sheet_index: Ragic sheet index.
        plan: Aggregation plan from aggregation_builder.
        field_label_map: field_id → human label mapping.
        pre_filters: Optional Ragic API-level WHERE filters.

    Returns:
        PandasEngineResult with aggregated data.
    """
    start = time.monotonic()

    try:
        query_result = await client.get_all_records(
            tab_path=tab_path,
            sheet_index=sheet_index,
            where=pre_filters,
        )
    except Exception as exc:
        elapsed = (time.monotonic() - start) * 1000
        return PandasEngineResult(
            execution_time_ms=round(elapsed, 2),
            success=False,
            error_message=f"Ragic API 撈取失敗：{exc}",
        )

    source_count = query_result.record_count
    if source_count == 0:
        elapsed = (time.monotonic() - start) * 1000
        return PandasEngineResult(
            execution_time_ms=round(elapsed, 2),
            source_record_count=0,
            success=True,
            error_message="查詢完成，但來源資料為空",
        )

    df = records_to_dataframe(query_result, field_label_map)
    df = _apply_pre_filters(df, plan.filters, field_label_map)

    if df.empty:
        elapsed = (time.monotonic() - start) * 1000
        return PandasEngineResult(
            execution_time_ms=round(elapsed, 2),
            source_record_count=source_count,
            success=True,
            error_message="篩選後無符合條件的資料",
        )

    agg_df = _execute_aggregation(df, plan, field_label_map)

    if agg_df.empty:
        elapsed = (time.monotonic() - start) * 1000
        return PandasEngineResult(
            execution_time_ms=round(elapsed, 2),
            source_record_count=source_count,
            success=False,
            error_message="聚合操作未產生有效結果（欄位不存在或非數值）",
        )

    if plan.order_by:
        order_col = field_label_map.get(plan.order_by, plan.order_by)
        order_candidates = [c for c in agg_df.columns if order_col in c]
        if order_candidates:
            ascending = plan.order_direction == "ASC"
            agg_df = agg_df.sort_values(order_candidates[0], ascending=ascending)

    if plan.limit and plan.limit < len(agg_df):
        agg_df = agg_df.head(plan.limit)

    records = agg_df.to_dict(orient="records")
    columns = list(agg_df.columns)

    elapsed = (time.monotonic() - start) * 1000

    logger.info(
        "Path B aggregation: %d source → %d rows, %.0fms",
        source_count,
        len(records),
        elapsed,
    )

    return PandasEngineResult(
        data=records,
        columns=columns,
        row_count=len(records),
        group_by_fields=[
            field_label_map.get(f, f) for f in plan.group_by_fields
        ],
        metrics_applied=plan.metrics,
        execution_time_ms=round(elapsed, 2),
        source_record_count=source_count,
        success=True,
    )
