"""
@file        router.py
@description FastAPI routes for RagicDataAgent — query + schema + intent + NL endpoints.
@lastUpdate  2026-04-13 06:16:12
@author      Daniel Chung
@version     2.2.0
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Optional, Union

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from data_agent.ragic.client import RagicAPIClient
from data_agent.ragic.config_loader import RagicConfigLoader
from data_agent.ragic.exceptions import (
    RagicAuthError,
    RagicError,
    RagicForbiddenError,
    RagicNotFoundError,
    RagicRateLimitError,
    RagicTimeoutError,
)
from data_agent.ragic.formatter import to_csv_bytes, to_excel_bytes
from data_agent.ragic.models import (
    IntentSearchRequest,
    IntentSearchResponse,
    IntentSearchResult,
    IntentUpsertRequest,
    NLClarification,
    NLIntentMatch,
    NLPostError,
    NLQueryMetadata,
    NLQueryRequest,
    NLQueryResponse,
    NLResultSet,
    NLResultStats,
    RagicConnectionConfig,
    RagicIntent,
    RagicOperator,
    RagicPagination,
    RagicQueryParams,
    RagicQueryResult,
    RagicRecord,
    RagicTableSchema,
    RagicWhereClause,
    SchemaSearchRequest,
    SchemaSearchResponse,
    SchemaSearchResult,
    SchemaUpsertRequest,
)
from data_agent.ragic.intent_store import IntentVectorStore
from data_agent.ragic.nl_parser import ParseResult, RagicNLParser
from data_agent.ragic.pandas_engine import fetch_and_aggregate
from data_agent.ragic.query_engine import RagicQueryEngine
from data_agent.ragic.query_router import RouteDecision, route_query_with_text
from data_agent.ragic.query_type_inferrer import infer_query_type
from data_agent.ragic.schema_linker import load_fields_from_arango
from data_agent.ragic.schema_store import RagicSchemaStore
from data_agent.ragic.schema_sync import RagicSchemaSync

import httpx as _httpx

logger = logging.getLogger(__name__)

router = APIRouter()

_DEFAULT_ACCOUNT = os.getenv("RAGIC_DEFAULT_ACCOUNT", "2025shianyong")
_DEFAULT_SERVER = os.getenv("RAGIC_DEFAULT_SERVER", "ap15")
_DEFAULT_API_KEY = os.getenv("RAGIC_API_KEY", "")

_ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
_ARANGO_DB = os.getenv("ARANGO_DATABASE", "abc_desktop")
_ARANGO_USER = os.getenv("ARANGO_USER", "root")
_ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "abc_desktop_2026")


async def _resolve_da_table_key(table_key: str) -> tuple[str, int] | None:
    """Resolve a da_tables _key (e.g. 'ERP_13') to legacy (tab_path, sheet_number).

    Looks up da_tables.source_meta.tab and source_meta.sheet_number in ArangoDB.
    Returns None if the table is not found or source_meta is missing.
    """
    aql = (
        "FOR d IN da_tables FILTER d._key == @key "
        "RETURN { tab: d.source_meta.tab, sheet_number: d.source_meta.sheet_number }"
    )
    try:
        async with _httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{_ARANGO_URL}/_db/{_ARANGO_DB}/_api/cursor",
                json={"query": aql, "bindVars": {"key": table_key}},
                auth=(_ARANGO_USER, _ARANGO_PASSWORD),
            )
            if resp.status_code not in (200, 201):
                return None
            results: list[dict[str, object]] = resp.json().get("result", [])
            if not results:
                return None
            row = results[0]
            tab = row.get("tab")
            sheet_raw = row.get("sheet_number")
            if not tab or sheet_raw is None:
                return None
            return str(tab), int(sheet_raw)
    except (ValueError, TypeError, _httpx.HTTPError) as exc:
        logger.warning("Failed to resolve da_table_key %s: %s", table_key, exc)
        return None

_config_loader = RagicConfigLoader()


async def _build_client_async(
    account: str | None = None,
    server: str | None = None,
    api_key: str | None = None,
) -> RagicAPIClient:
    target_account = account or _DEFAULT_ACCOUNT

    if api_key:
        config = RagicConnectionConfig(
            account=target_account,
            api_key=api_key,
            server_prefix=server or _DEFAULT_SERVER,
        )
        return RagicAPIClient(config)

    conn = await _config_loader.get_connection(target_account)
    if conn:
        return RagicAPIClient(conn)

    config = RagicConnectionConfig(
        account=target_account,
        api_key=_DEFAULT_API_KEY,
        server_prefix=server or _DEFAULT_SERVER,
    )
    return RagicAPIClient(config)


def _build_client(
    account: str | None = None,
    server: str | None = None,
    api_key: str | None = None,
) -> RagicAPIClient:
    config = RagicConnectionConfig(
        account=account or _DEFAULT_ACCOUNT,
        api_key=api_key or _DEFAULT_API_KEY,
        server_prefix=server or _DEFAULT_SERVER,
    )
    return RagicAPIClient(config)


class DirectQueryRequest(BaseModel):
    """Request body for direct Ragic query via POST."""

    tab_path: str = Field(..., description="Tab path, e.g. 'configuration-file'")
    sheet_index: int = Field(..., description="Sheet number within the tab")
    where: list[RagicWhereClause] = Field(default_factory=list)
    limit: int = Field(default=1000, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
    order_field: Optional[str] = None
    order_direction: str = Field(default="DESC")
    naming: str = Field(default="EID")
    subtables: Optional[int] = None


class DirectQueryResponse(BaseModel):
    """Wrapper for direct query result."""

    code: int = 0
    data: RagicQueryResult


class HealthResponse(BaseModel):
    """Health check result."""

    status: str
    service: str = "ragic_data_agent"
    ragic_ok: bool = False
    ragic_account: str = ""
    ragic_server: str = ""
    error: str = ""


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    if not _DEFAULT_API_KEY:
        return HealthResponse(
            status="degraded",
            error="RAGIC_API_KEY not configured",
        )

    client = _build_client()
    result = await client.check_health()

    if result.get("ok"):
        return HealthResponse(
            status="ok",
            ragic_ok=True,
            ragic_account=str(result.get("account", "")),
            ragic_server=str(result.get("server", "")),
        )

    return HealthResponse(
        status="degraded",
        error=str(result.get("error", "unknown")),
    )


@router.post("/query/records", response_model=DirectQueryResponse)
async def query_records(request: DirectQueryRequest) -> DirectQueryResponse:
    """Query Ragic records with structured parameters."""
    if not _DEFAULT_API_KEY:
        raise HTTPException(status_code=500, detail="RAGIC_API_KEY not configured")

    client = _build_client()

    params = RagicQueryParams(
        where=request.where,
        limit=request.limit,
        offset=request.offset,
        order_field=request.order_field,
        order_direction=request.order_direction,  # type: ignore[arg-type]
        naming=request.naming,
        subtables=request.subtables,
    )

    try:
        result = await client.get_records(
            tab_path=request.tab_path,
            sheet_index=request.sheet_index,
            params=params,
        )
    except RagicError as exc:
        raise HTTPException(
            status_code=_ragic_error_to_http(exc),
            detail={"code": exc.code, "message": str(exc)},
        )

    return DirectQueryResponse(data=result)


@router.get("/query/records")
async def query_records_get(
    tab_path: str = Query(..., description="Tab path, e.g. 'configuration-file'"),
    sheet_index: int = Query(..., description="Sheet number"),
    where: Optional[str] = Query(None, description="Filter: field_id,op,value"),
    limit: int = Query(1000, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    order: Optional[str] = Query(None, description="field_id,ASC|DESC"),
    naming: str = Query("EID"),
    subtables: Optional[int] = Query(None),
    connection: Optional[str] = Query(None, description="Account name override"),
) -> DirectQueryResponse:
    """Query Ragic records via GET with query-string parameters."""
    if not _DEFAULT_API_KEY:
        raise HTTPException(status_code=500, detail="RAGIC_API_KEY not configured")

    client = _build_client(account=connection)

    where_clauses: list[RagicWhereClause] = []
    if where:
        parts = where.split(",", 2)
        if len(parts) == 3:
            try:
                op = RagicOperator(parts[1].strip())
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid operator '{parts[1]}'. "
                    f"Valid: {[e.value for e in RagicOperator]}",
                )
            where_clauses.append(
                RagicWhereClause(
                    field_id=parts[0].strip(),
                    operator=op,
                    value=parts[2].strip(),
                )
            )

    order_field: str | None = None
    order_dir = "DESC"
    if order:
        order_parts = order.split(",", 1)
        order_field = order_parts[0].strip()
        if len(order_parts) > 1:
            order_dir = order_parts[1].strip().upper()

    params = RagicQueryParams(
        where=where_clauses,
        limit=limit,
        offset=offset,
        order_field=order_field,
        order_direction=order_dir,  # type: ignore[arg-type]
        naming=naming,
        subtables=subtables,
    )

    try:
        result = await client.get_records(
            tab_path=tab_path,
            sheet_index=sheet_index,
            params=params,
        )
    except RagicError as exc:
        raise HTTPException(
            status_code=_ragic_error_to_http(exc),
            detail={"code": exc.code, "message": str(exc)},
        )

    return DirectQueryResponse(data=result)


def _ragic_error_to_http(exc: RagicError) -> int:
    """Map RagicError subclass to HTTP status code."""
    mapping: dict[type, int] = {
        RagicAuthError: 401,
        RagicForbiddenError: 403,
        RagicNotFoundError: 404,
        RagicRateLimitError: 429,
        RagicTimeoutError: 504,
    }
    return mapping.get(type(exc), 502)


_schema_store = RagicSchemaStore()


class SchemaUpsertResponse(BaseModel):
    """Response after upserting schemas."""

    upserted_count: int
    collection: str = "ragic_schemas"
    status: str = "ok"


class SchemaListResponse(BaseModel):
    """Response listing schemas."""

    schemas: list[RagicTableSchema] = Field(default_factory=list)
    total: int = 0


class SchemaCountResponse(BaseModel):
    """Response with schema count."""

    count: int = 0
    collection: str = "ragic_schemas"


@router.post("/schema/upsert", response_model=SchemaUpsertResponse)
async def schema_upsert(request: SchemaUpsertRequest) -> SchemaUpsertResponse:
    """Upsert table schemas into Qdrant (embed + store)."""
    try:
        count = await _schema_store.upsert(request.schemas)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Schema upsert failed: {exc}")
    return SchemaUpsertResponse(upserted_count=count)


@router.post("/schema/search", response_model=SchemaSearchResponse)
async def schema_search(request: SchemaSearchRequest) -> SchemaSearchResponse:
    """Search schemas by natural language query."""
    try:
        hits = await _schema_store.search(
            query=request.query,
            account=request.account,
            top_k=request.top_k,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Schema search failed: {exc}")

    results: list[SchemaSearchResult] = []
    for hit in hits:
        payload = hit.get("payload", {})
        if not isinstance(payload, dict):
            continue
        schema = RagicSchemaStore.payload_to_schema(payload)
        raw_score = hit.get("score", 0.0)
        hit_score = float(raw_score) if isinstance(raw_score, (int, float)) else 0.0
        results.append(
            SchemaSearchResult(
                table_key=schema.table_key,
                table_name=schema.table_name,
                account=schema.account,
                score=hit_score,
                schema_data=schema,
            )
        )

    return SchemaSearchResponse(
        query=request.query, results=results, total=len(results)
    )


@router.get("/schema/list", response_model=SchemaListResponse)
async def schema_list(
    account: Optional[str] = Query(None, description="Filter by account"),
    limit: int = Query(100, ge=1, le=500),
) -> SchemaListResponse:
    """List all stored schemas."""
    try:
        points = await _schema_store.list_all(account=account, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Schema list failed: {exc}")

    schemas: list[RagicTableSchema] = []
    for point in points:
        payload = point.get("payload", {})
        if isinstance(payload, dict):
            schemas.append(RagicSchemaStore.payload_to_schema(payload))

    return SchemaListResponse(schemas=schemas, total=len(schemas))


@router.get("/schema/count", response_model=SchemaCountResponse)
async def schema_count() -> SchemaCountResponse:
    try:
        total = await _schema_store.count()
    except Exception:
        total = 0
    return SchemaCountResponse(count=total)


# ---------------------------------------------------------------------------
# Intent endpoints
# ---------------------------------------------------------------------------

_intent_store = IntentVectorStore()


class IntentUpsertResponse(BaseModel):
    upserted_count: int
    collection: str = "ragic_intents"
    status: str = "ok"


class IntentListResponse(BaseModel):
    intents: list[RagicIntent] = Field(default_factory=list)
    total: int = 0


class IntentCountResponse(BaseModel):
    count: int = 0
    collection: str = "ragic_intents"


@router.post("/intent/upsert", response_model=IntentUpsertResponse)
async def intent_upsert(request: IntentUpsertRequest) -> IntentUpsertResponse:
    try:
        count = await _intent_store.upsert(request.intents)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Intent upsert failed: {exc}")
    return IntentUpsertResponse(upserted_count=count)


@router.post("/intent/search", response_model=IntentSearchResponse)
async def intent_search(request: IntentSearchRequest) -> IntentSearchResponse:
    try:
        hits = await _intent_store.search(
            query=request.query,
            account=request.account,
            top_k=request.top_k,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Intent search failed: {exc}")

    results: list[IntentSearchResult] = []
    for hit in hits:
        payload = hit.get("payload", {})
        if not isinstance(payload, dict):
            continue
        intent = IntentVectorStore.payload_to_intent(payload)
        raw_score = hit.get("score", 0.0)
        hit_score = float(raw_score) if isinstance(raw_score, (int, float)) else 0.0
        results.append(
            IntentSearchResult(
                intent_id=intent.intent_id,
                account=intent.account,
                score=hit_score,
                intent_data=intent,
            )
        )

    best = results[0] if results else None

    return IntentSearchResponse(
        query=request.query,
        results=results,
        total=len(results),
        best_match=best,
    )


@router.get("/intent/list", response_model=IntentListResponse)
async def intent_list(
    account: Optional[str] = Query(None, description="Filter by account"),
    limit: int = Query(100, ge=1, le=500),
) -> IntentListResponse:
    try:
        points = await _intent_store.list_all(account=account, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Intent list failed: {exc}")

    intents: list[RagicIntent] = []
    for point in points:
        payload = point.get("payload", {})
        if isinstance(payload, dict):
            intents.append(IntentVectorStore.payload_to_intent(payload))

    return IntentListResponse(intents=intents, total=len(intents))


@router.get("/intent/count", response_model=IntentCountResponse)
async def intent_count() -> IntentCountResponse:
    try:
        total = await _intent_store.count()
    except Exception:
        total = 0
    return IntentCountResponse(count=total)


# ---------------------------------------------------------------------------
# NL query endpoint
# ---------------------------------------------------------------------------

_nl_parser = RagicNLParser(
    intent_store=_intent_store,
)

_query_engine = RagicQueryEngine()


_FRIENDLY_RAGIC_MESSAGES: dict[type, str] = {
    RagicTimeoutError: "查詢逾時，Ragic 伺服器回應較慢，請稍後再試",
    RagicAuthError: "API 金鑰已失效，請至系統設定更新 Ragic 連線資訊",
    RagicForbiddenError: "權限不足，無法存取此 Ragic 表單",
    RagicNotFoundError: "找不到對應的 Ragic 表單，請確認表單路徑是否正確",
    RagicRateLimitError: "查詢頻率過高（Ragic 限制每秒 5 次），請稍候再試",
}

_CLARIFICATION_SUGGESTIONS = [
    "查詢上個月的進貨單",
    "列出所有採購訂單",
    "查詢庫存表",
    "查詢近 30 天收貨單",
]


def _estimate_tokens(records: list[RagicRecord]) -> int:
    if not records:
        return 0
    raw = json.dumps([r.model_dump() for r in records], ensure_ascii=False)
    return len(raw) // 4


async def _handle_path_b(
    request: NLQueryRequest,
    parsed: ParseResult,
    route_decision: RouteDecision,
    account: str,
    tab_path: str,
    sheet_index: int,
    intent_block: NLIntentMatch | None,
    confidence: str,
    start: float,
) -> NLQueryResponse:
    """Execute Path B: fetch Ragic data → pandas aggregation → return result."""
    agg_result = route_decision.aggregation_result
    if not agg_result or not agg_result.plan:
        return NLQueryResponse(
            code=2,
            status="error",
            post_error=NLPostError(
                error_code=2,
                raw_error="aggregation plan is None",
                message="聚合計畫生成失敗",
            ),
            intent=intent_block,
        )

    client = await _build_client_async(account=account)

    fields = await load_fields_from_arango(parsed.table_key)
    field_label_map = {f["field_id"]: f["field_name"] for f in fields}

    pandas_result = await fetch_and_aggregate(
        client=client,
        tab_path=tab_path,
        sheet_index=sheet_index,
        plan=agg_result.plan,
        field_label_map=field_label_map,
    )

    if not pandas_result.success:
        return NLQueryResponse(
            code=2,
            status="error",
            post_error=NLPostError(
                error_code=2,
                raw_error=pandas_result.error_message,
                message=f"聚合查詢失敗：{pandas_result.error_message}",
            ),
            intent=intent_block,
            metadata=NLQueryMetadata(
                connection=account,
                table_key=parsed.table_key,
                query=request.query,
                translated_params=route_decision.translated_params,
                path_used=route_decision.path_used,
            ),
        )

    total_ms = round((time.monotonic() - start) * 1000, 2)

    agg_records = [
        RagicRecord(ragic_id=f"agg_{i}", fields=row)
        for i, row in enumerate(pandas_result.data)
    ]

    post_error_block: NLPostError | None = None
    if pandas_result.row_count == 0:
        post_error_block = NLPostError(
            error_code=0,
            message=(
                "聚合查詢完成，但未產生任何結果。"
                "可能原因：1. 該時段無相關記錄 2. 篩選條件過嚴"
            ),
        )

    return NLQueryResponse(
        code=0,
        status="success",
        result=NLResultSet(
            records=agg_records,
            record_count=pandas_result.row_count,
            pagination=RagicPagination(
                offset=0,
                limit=pandas_result.row_count,
                returned_count=pandas_result.row_count,
                has_more=False,
            ),
            field_labels=field_label_map,
            execution_time_ms=total_ms,
            stats=NLResultStats(
                total_fields=len(pandas_result.columns),
                estimated_tokens=_estimate_tokens(agg_records),
            ),
        ),
        intent=intent_block,
        post_error=post_error_block,
        metadata=NLQueryMetadata(
            connection=account,
            table_key=parsed.table_key,
            output_format=request.output_format,
            query=request.query,
            translated_params=route_decision.translated_params,
            path_used=route_decision.path_used,
        ),
    )


@router.post("/query", response_model=None)
async def nl_query(request: NLQueryRequest) -> Union[NLQueryResponse, Response]:
    account = request.connection_name or _DEFAULT_ACCOUNT
    start = time.monotonic()

    stripped = request.query.strip()
    if len(stripped) == 0:
        return NLQueryResponse(
            code=1,
            status="clarification_needed",
            clarification=NLClarification(
                message="請輸入查詢內容",
                suggestions=_CLARIFICATION_SUGGESTIONS,
            ),
        )
    if len(stripped) < 4:
        return NLQueryResponse(
            code=1,
            status="clarification_needed",
            clarification=NLClarification(
                message="查詢內容過短，請提供更詳細的描述",
                suggestions=_CLARIFICATION_SUGGESTIONS,
            ),
        )
    if not re.search(r"[\u4e00-\u9fff]", stripped) and not re.search(r"[a-zA-Z]", stripped):
        return NLQueryResponse(
            code=1,
            status="clarification_needed",
            clarification=NLClarification(
                message="無法識別有效的查詢語句",
                suggestions=_CLARIFICATION_SUGGESTIONS,
            ),
        )

    try:
        parsed = await _nl_parser.parse(
            query=stripped,
            account=account,
            table_key=request.table_key,
            options=request.options,
        )
    except Exception as exc:
        return NLQueryResponse(
            code=2,
            status="error",
            post_error=NLPostError(
                error_code=2,
                raw_error=str(exc),
                message=f"自然語言解析失敗：{exc}",
            ),
        )

    confidence = parsed.confidence

    intent_block: NLIntentMatch | None = None
    if parsed.intent_matched:
        intent_block = NLIntentMatch(
            intent_id=parsed.intent_matched.intent_id,
            score=parsed.intent_matched.score,
            confidence=confidence,
            action=parsed.intent_matched.action,
            table_key=parsed.intent_matched.table_key,
        )

    if parsed.date_clarification_needed:
        return NLQueryResponse(
            code=6,
            status="clarification_needed",
            clarification=NLClarification(
                message="查詢包含日期描述但未提供具體日期範圍，請提供明確的起迄日期",
                suggestions=[
                    "請提供具體日期範圍，例如：2026/03/01 ~ 2026/03/31",
                    "查詢 2026年3月 的進貨單",
                    "查詢 2026/03/01 到 2026/03/31 的進貨單",
                ],
            ),
            intent=intent_block,
            metadata=NLQueryMetadata(
                connection=account,
                table_key=parsed.table_key,
                query=request.query,
                translated_params=parsed.translated_params,
            ),
        )

    if confidence == "low":
        return NLQueryResponse(
            code=5,
            status="clarification_needed",
            clarification=NLClarification(
                message="無法理解您的查詢意圖，請嘗試更具體的描述",
                suggestions=_CLARIFICATION_SUGGESTIONS,
            ),
            intent=intent_block,
            metadata=NLQueryMetadata(
                connection=account,
                query=request.query,
                translated_params=parsed.translated_params,
            ),
        )

    if not parsed.table_key:
        return NLQueryResponse(
            code=3,
            status="clarification_needed",
            clarification=NLClarification(
                message="無法判斷要查詢的表格，請指定 table_key 或新增對應 Intent",
                suggestions=_CLARIFICATION_SUGGESTIONS,
            ),
            intent=intent_block,
            metadata=NLQueryMetadata(
                connection=account,
                query=request.query,
                translated_params=parsed.translated_params,
            ),
        )

    parts = parsed.table_key.rsplit("/", 1)
    if len(parts) == 2:
        tab_path = parts[0]
        try:
            sheet_index = int(parts[1])
        except ValueError:
            return NLQueryResponse(
                code=4,
                status="error",
                post_error=NLPostError(
                    error_code=4,
                    raw_error=f"sheet_index not a number: {parts[1]}",
                    message=f"sheet_index 不是數字：{parts[1]}",
                ),
                intent=intent_block,
            )
    else:
        resolved = await _resolve_da_table_key(parsed.table_key)
        if resolved is None:
            return NLQueryResponse(
                code=4,
                status="error",
                post_error=NLPostError(
                    error_code=4,
                    raw_error=f"table_key not found in da_tables: {parsed.table_key}",
                    message=f"找不到表格 '{parsed.table_key}' 的來源資訊",
                ),
                intent=intent_block,
            )
        tab_path, sheet_index = resolved

    parsed.query_type = await infer_query_type(
        query=stripped,
        table_key=parsed.table_key,
    )

    route_decision = await route_query_with_text(parsed, stripped)
    routed_params = route_decision.translated_params

    if route_decision.path_used == "pandas_engine" and route_decision.aggregation_result:
        return await _handle_path_b(
            request=request,
            parsed=parsed,
            route_decision=route_decision,
            account=account,
            tab_path=tab_path,
            sheet_index=sheet_index,
            intent_block=intent_block,
            confidence=confidence,
            start=start,
        )

    query_params = _nl_parser.translated_to_query_params(routed_params)

    if request.options.include_subtables:
        query_params.subtables = 1

    client = await _build_client_async(account=account)

    try:
        engine_result = await _query_engine.execute(
            client=client,
            tab_path=tab_path,
            sheet_index=sheet_index,
            params=query_params,
            account=account,
            auto_paginate=request.options.auto_paginate,
        )
    except RagicError as exc:
        friendly = _FRIENDLY_RAGIC_MESSAGES.get(
            type(exc),
            f"查詢過程中發生錯誤：{exc}。請稍後重試",
        )
        return NLQueryResponse(
            code=_ragic_error_to_http(exc),
            status="error",
            post_error=NLPostError(
                error_code=_ragic_error_to_http(exc),
                raw_error=str(exc),
                message=friendly,
            ),
            intent=intent_block,
            metadata=NLQueryMetadata(
                connection=account,
                table_key=parsed.table_key,
                query=request.query,
                translated_params=routed_params,
                path_used=route_decision.path_used,
            ),
        )

    field_labels = (
        engine_result.records[0].field_labels if engine_result.records else {}
    )

    fmt = request.output_format.lower()
    if fmt == "csv":
        csv_bytes = to_csv_bytes(engine_result.records, field_labels)
        return Response(
            content=csv_bytes,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": "attachment; filename=ragic_export.csv",
            },
        )

    if fmt == "excel":
        xlsx_bytes = to_excel_bytes(engine_result.records, field_labels)
        return Response(
            content=xlsx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": "attachment; filename=ragic_export.xlsx",
            },
        )

    total_ms = round((time.monotonic() - start) * 1000, 2)

    records_as_ragic = [
        RagicRecord(ragic_id=r.ragic_id, fields=r.fields)
        for r in engine_result.records
    ]

    post_error_block: NLPostError | None = None
    if engine_result.record_count == 0:
        post_error_block = NLPostError(
            error_code=0,
            message=(
                "查詢完成，但未找到符合條件的資料。"
                "可能原因：1. 該時段無相關記錄 2. 篩選條件過嚴"
            ),
        )

    clarification_block: NLClarification | None = None
    if confidence == "medium":
        table_name = parsed.intent_matched.table_key if parsed.intent_matched else parsed.table_key
        clarification_block = NLClarification(
            message=f"系統推測您想查詢「{table_name}」，若不正確請換方式描述",
        )

    estimated_tokens = _estimate_tokens(records_as_ragic)

    return NLQueryResponse(
        code=0,
        status="success",
        clarification=clarification_block,
        result=NLResultSet(
            records=records_as_ragic,
            record_count=engine_result.record_count,
            pagination=RagicPagination(
                offset=query_params.offset,
                limit=query_params.limit,
                returned_count=engine_result.record_count,
                has_more=engine_result.has_more,
            ),
            field_labels=field_labels,
            execution_time_ms=total_ms,
            stats=NLResultStats(
                total_fields=len(field_labels),
                estimated_tokens=estimated_tokens,
            ),
        ),
        intent=intent_block,
        post_error=post_error_block,
        metadata=NLQueryMetadata(
            connection=account,
            table_key=parsed.table_key,
            output_format=request.output_format,
            query=request.query,
            translated_params=routed_params,
            path_used=route_decision.path_used,
        ),
    )


# ---------------------------------------------------------------------------
# Config management endpoints
# ---------------------------------------------------------------------------


class ConfigConnectionInfo(BaseModel):
    account: str
    server_prefix: str
    enabled: bool
    description: str


class ConfigListResponse(BaseModel):
    connections: list[ConfigConnectionInfo] = Field(default_factory=list)
    total: int = 0
    source: str = ""


class ConfigReloadResponse(BaseModel):
    status: str = "ok"
    message: str = ""


@router.get("/config/connections", response_model=ConfigListResponse)
async def config_list_connections() -> ConfigListResponse:
    connections = await _config_loader.get_all_connections()
    items = [
        ConfigConnectionInfo(
            account=c.account,
            server_prefix=c.server_prefix,
            enabled=c.enabled,
            description=c.description,
        )
        for c in connections
    ]
    source = "ragic" if any(c.description != "env-fallback" for c in connections) else "env-fallback"
    return ConfigListResponse(
        connections=items, total=len(items), source=source
    )


@router.post("/config/reload", response_model=ConfigReloadResponse)
async def config_reload() -> ConfigReloadResponse:
    _config_loader.reload()
    return ConfigReloadResponse(message="Config cache cleared, will reload on next request")


# ---------------------------------------------------------------------------
# Schema sync endpoints
# ---------------------------------------------------------------------------

_schema_sync = RagicSchemaSync(schema_store=_schema_store)


class SchemaSyncRequest(BaseModel):
    connection_name: Optional[str] = None
    table_keys: list[str] = Field(
        ..., description="List of table keys, e.g. ['configuration-file/10']"
    )


class SchemaSyncResult(BaseModel):
    table_key: str
    table_name: str
    field_count: int


class SchemaSyncResponse(BaseModel):
    synced: list[SchemaSyncResult] = Field(default_factory=list)
    total: int = 0
    status: str = "ok"
    error: str = ""


@router.post("/schema/sync", response_model=SchemaSyncResponse)
async def schema_sync(request: SchemaSyncRequest) -> SchemaSyncResponse:
    account = request.connection_name or _DEFAULT_ACCOUNT
    client = await _build_client_async(account=account)

    try:
        schemas = await _schema_sync.sync_tables(client, request.table_keys)
    except Exception as exc:
        return SchemaSyncResponse(
            status="error", error=f"Schema sync failed: {exc}"
        )

    results = [
        SchemaSyncResult(
            table_key=s.table_key,
            table_name=s.table_name,
            field_count=len(s.fields),
        )
        for s in schemas
    ]
    return SchemaSyncResponse(synced=results, total=len(results))
