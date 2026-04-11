"""
@file        router_import.py
@description FastAPI routes for Phase 9-11: MD import, graph query, multi-step query.
@lastUpdate  2026-04-11 17:52:08
@author      Daniel Chung
@version     1.2.0
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
from data_agent.ragic.intent_store import RagicIntentStore
from data_agent.ragic.models_phase9 import (
    GraphQueryResult,
    ImportResult,
    MultiStepQuery,
    MultiStepResult,
    StepResult,
)
from data_agent.ragic.multi_step_orchestrator import MultiStepOrchestrator
from data_agent.ragic.query_engine import RagicQueryEngine
from data_agent.ragic.result_merger import ResultMerger
from data_agent.ragic.schema_store import RagicSchemaStore
from data_agent.ragic.step_executor import RagicStepExecutor

logger = logging.getLogger(__name__)

router = APIRouter()


class _StepExecutorAdapter:

    def __init__(self, real: RagicStepExecutor) -> None:
        self._real = real

    async def execute(
        self, request: MultiStepQuery | StepResult
    ) -> StepResult:
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
_intent_store = RagicIntentStore()
_arango_writer = RagicArangoWriter()
_graph_query = RagicGraphQuery()
_config_loader = RagicConfigLoader()
_query_engine = RagicQueryEngine(_schema_store)
_step_executor = RagicStepExecutor(_query_engine, _config_loader)
_result_merger = ResultMerger()
_import_orchestrator = RagicImportOrchestrator(_schema_store, _intent_store, _arango_writer)
_multi_step_orchestrator = MultiStepOrchestrator(
    graph_query=_graph_query,
    step_executor=_StepExecutorAdapter(_step_executor),
    result_merger=_result_merger,
)


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
