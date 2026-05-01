"""
@file        router_import.py
@description FastAPI routes for Phase 9-11: MD import, graph query, multi-step query.
@lastUpdate  2026-04-11 20:39:24
@author      Daniel Chung
@version     1.3.0
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from data_agent.ragic.arango_writer import RagicArangoWriter
from data_agent.ragic.config_loader import RagicConfigLoader
from data_agent.ragic.graph_query import RagicGraphQuery
from data_agent.ragic.import_orchestrator import RagicImportOrchestrator
from data_agent.ragic.intent_store import IntentVectorStore
from data_agent.ragic.models_phase9 import (
    GraphQueryResult,
    ImportResult,
    MultiStepQuery,
    MultiStepResult,
    StepResult,
)
from data_agent.ragic.multi_step_orchestrator import MultiStepOrchestrator
from data_agent.ragic.query_engine import RagicQueryEngine
from data_agent.ragic.record_tracer import RecordTracer
from data_agent.ragic.result_merger import ResultMerger
from data_agent.ragic.schema_store import RagicSchemaStore
from data_agent.ragic.step_executor import RagicStepExecutor

logger = logging.getLogger(__name__)

router = APIRouter()


class _StepExecutorAdapter:
    def __init__(self, real: RagicStepExecutor) -> None:
        self._real = real

    async def execute(self, request: MultiStepQuery | StepResult) -> StepResult:
        if isinstance(request, MultiStepQuery):
            return StepResult(
                step_index=0,
                table_name=request.query,
            )
        return StepResult(
            step_index=request.step_index,
            table_name=request.table_name,
        )


_schema_store = RagicSchemaStore()
_intent_store = IntentVectorStore()
_arango_writer = RagicArangoWriter()
_graph_query = RagicGraphQuery()
_config_loader = RagicConfigLoader()
_query_engine = RagicQueryEngine()
_step_executor = RagicStepExecutor(_query_engine, _config_loader)
_result_merger = ResultMerger()
_import_orchestrator = RagicImportOrchestrator(
    _schema_store, _intent_store, _arango_writer
)
_multi_step_orchestrator = MultiStepOrchestrator(
    graph_query=_graph_query,
    step_executor=_StepExecutorAdapter(_step_executor),
    result_merger=_result_merger,
)
_record_tracer = RecordTracer(graph_query=_graph_query, config_loader=_config_loader)


class ImportMDRequest(BaseModel):
    account: str
    content: str


class ImportMDResponse(BaseModel):
    code: int = 0
    message: str = "OK"
    data: Optional[ImportResult] = None


class GraphRelatedResponse(BaseModel):
    code: int = 0
    data: Optional[GraphQueryResult] = None


class GraphPathResponse(BaseModel):
    code: int = 0
    data: Optional[list[dict[str, object]]] = None


class GraphAllRelationsResponse(BaseModel):
    code: int = 0
    data: list[dict[str, object]] = Field(default_factory=list)


@router.post("/schema/import-md", response_model=ImportMDResponse)
async def import_md_schema(req: ImportMDRequest) -> ImportMDResponse:
    try:
        result = await _import_orchestrator.run_import(req.content, req.account)
        return ImportMDResponse(data=result)
    except Exception as e:
        logger.exception("MD import failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/graph/related-tables", response_model=GraphRelatedResponse)
async def get_related_tables(
    table_name: str = Query(...),
    account: str = Query(...),
    depth: int = Query(default=1, ge=1, le=5),
) -> GraphRelatedResponse:
    try:
        result = await _graph_query.get_related_tables(table_name, account, depth)
        return GraphRelatedResponse(data=result)
    except Exception as e:
        logger.exception("Graph query failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/graph/path", response_model=GraphPathResponse)
async def find_graph_path(
    from_table: str = Query(...),
    to_table: str = Query(...),
    account: str = Query(...),
    max_depth: int = Query(default=4, ge=1, le=10),
) -> GraphPathResponse:
    try:
        path = await _graph_query.find_path(from_table, to_table, account, max_depth)
        if path is None:
            raise HTTPException(status_code=404, detail="No path found between tables")
        return GraphPathResponse(data=[e.model_dump() for e in path])
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Path finding failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/graph/all-relations", response_model=GraphAllRelationsResponse)
async def get_all_relations(
    account: str = Query(...),
) -> GraphAllRelationsResponse:
    try:
        relations = await _graph_query.get_all_relations(account)
        return GraphAllRelationsResponse(data=[r.model_dump() for r in relations])
    except Exception as e:
        logger.exception("Get all relations failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


class IntentListItem(BaseModel):
    intent_id: str = ""
    account: str = ""
    description: str = ""
    action: str = "list"
    table_key: str = ""
    nl_patterns: list[str] = Field(default_factory=list)
    api_template: str = ""


class IntentListResponse(BaseModel):
    code: int = 0
    data: list[IntentListItem] = Field(default_factory=list)
    total: int = 0


@router.get("/intents", response_model=IntentListResponse)
async def list_ragic_intents(
    account: str = Query(...),
    limit: int = Query(default=500, ge=1, le=2000),
) -> IntentListResponse:
    try:
        points = await _intent_store.list_all(account=account, limit=limit)
        items: list[IntentListItem] = []
        for pt in points:
            payload = pt.get("payload", {})
            if not isinstance(payload, dict):
                continue
            nl_raw = payload.get("nl_patterns", [])
            nl_list = [str(p) for p in nl_raw] if isinstance(nl_raw, list) else []
            items.append(
                IntentListItem(
                    intent_id=str(payload.get("intent_id", "")),
                    account=str(payload.get("account", "")),
                    description=str(payload.get("description", "")),
                    action=str(payload.get("action", "list")),
                    table_key=str(payload.get("table_key", "")),
                    nl_patterns=nl_list,
                    api_template=str(payload.get("api_template", "")),
                )
            )
        return IntentListResponse(data=items, total=len(items))
    except Exception as e:
        logger.exception("List ragic intents failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


class MultiStepQueryResponse(BaseModel):
    code: int = 0
    data: Optional[MultiStepResult] = None
    error: Optional[str] = None


@router.post("/query/multi-step", response_model=MultiStepQueryResponse)
async def multi_step_query(req: MultiStepQuery) -> MultiStepQueryResponse:
    try:
        result = await _multi_step_orchestrator.execute(req)
        return MultiStepQueryResponse(data=result)
    except Exception as e:
        logger.exception("Multi-step query failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


class TraceRecordRequest(BaseModel):
    table_key: str
    record_id: str
    account: str
    depth: int = Field(default=3, ge=1, le=5)
    max_fan_out: int = Field(default=10, ge=1, le=50)


class TraceRecordResponse(BaseModel):
    code: int = 0
    data: Optional[dict[str, object]] = None
    error: Optional[str] = None


@router.post("/trace/record", response_model=TraceRecordResponse)
async def trace_record(req: TraceRecordRequest) -> TraceRecordResponse:
    try:
        graph = await _record_tracer.trace(
            table_key=req.table_key,
            record_id=req.record_id,
            account=req.account,
            depth=req.depth,
            max_fan_out=req.max_fan_out,
        )
        return TraceRecordResponse(data=graph.to_dict())
    except Exception as e:
        logger.exception("Record trace failed")
        raise HTTPException(status_code=500, detail=str(e)) from e
