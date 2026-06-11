"""
@file        router.py
@description FastAPI routes for trace_engine module — scenario traces, NL parsing, reports.
@lastUpdate  2026-05-17
@author      Daniel Chung
@version     1.0.0
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from data_agent.trace_engine.forward_engine import ForwardTraceEngine
from data_agent.trace_engine.models import (
    Report,
    TraceRequest,
    TraceResult,
    TraceScenario,
    TraceSummary,
)
from data_agent.trace_engine.nl_trace import handle_nl_parse
from data_agent.trace_engine.report_store import ReportStore
from data_agent.trace_engine.reverse_engine import ReverseTraceEngine

logger = logging.getLogger(__name__)

router = APIRouter()

_forward_engine: Optional[ForwardTraceEngine] = None
_reverse_engine: Optional[ReverseTraceEngine] = None
_report_store = ReportStore()

_FORWARD_SCENARIOS: frozenset[str] = frozenset({
    "shipment_batch",
    "incoming_batch",
    "product_full_history",
    "work_order",
})

_REVERSE_SCENARIOS: frozenset[str] = frozenset({
    "complaint_recall",
    "expiry_tracking",
    "quality_issue",
    "supplier_trace",
})

_ALL_SCENARIOS: frozenset[str] = _FORWARD_SCENARIOS | _REVERSE_SCENARIOS


def _validate_scenario(scenario_id: str) -> TraceScenario:
    if scenario_id not in _ALL_SCENARIOS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown scenario '{scenario_id}'. "
                f"Valid: {', '.join(sorted(_ALL_SCENARIOS))}"
            ),
        )
    return TraceScenario(scenario_id)


async def _get_forward_engine() -> ForwardTraceEngine:
    global _forward_engine
    if _forward_engine is None:
        from data_agent.ragic.config_loader import RagicConfigLoader
        from data_agent.ragic.graph_query import RagicGraphQuery
        from data_agent.ragic.record_tracer import RecordTracer

        config_loader = RagicConfigLoader()
        graph_query = RagicGraphQuery()
        tracer = RecordTracer(graph_query=graph_query, config_loader=config_loader)
        _forward_engine = ForwardTraceEngine(tracer=tracer, config_loader=config_loader)
    return _forward_engine


async def _get_reverse_engine() -> ReverseTraceEngine:
    global _reverse_engine
    if _reverse_engine is None:
        from data_agent.ragic.config_loader import RagicConfigLoader
        from data_agent.ragic.graph_query import RagicGraphQuery
        from data_agent.ragic.record_tracer import RecordTracer

        config_loader = RagicConfigLoader()
        graph_query = RagicGraphQuery()
        tracer = RecordTracer(graph_query=graph_query, config_loader=config_loader)
        _reverse_engine = ReverseTraceEngine(tracer=tracer, config_loader=config_loader)
    return _reverse_engine


class ScenarioTraceRequest(BaseModel):
    """Request body for running a scenario trace."""

    entry_batch: str = ""
    entry_table: str = ""
    depth: int = Field(default=3, ge=1, le=5)
    max_fan_out: int = Field(default=50, ge=1, le=200)
    options: dict[str, Any] = Field(default_factory=dict)


class NLParseRequest(BaseModel):
    """Request body for natural-language trace query parsing."""

    text: str


class ReportSaveRequest(BaseModel):
    """Request body for persisting a trace report."""

    name: str
    scenario: str
    entry_table: str = ""
    entry_batch: str = ""
    trace_result: Optional[dict[str, Any]] = None
    summary: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    created_by: str = "system"


@router.post("/scenario/{scenario_id}")
async def run_scenario(scenario_id: str, req: ScenarioTraceRequest) -> dict[str, Any]:
    """Execute a trace scenario by ID.

    Forward scenarios (1-4): shipment_batch, incoming_batch,
    product_full_history, work_order.

    Reverse scenarios (5-8): complaint_recall, expiry_tracking,
    quality_issue, supplier_trace.
    """
    scenario = _validate_scenario(scenario_id)

    trace_request = TraceRequest(
        scenario=scenario,
        entry_table=req.entry_table,
        entry_batch=req.entry_batch,
        depth=req.depth,
        max_fan_out=req.max_fan_out,
        options=req.options,
    )

    account = str(req.options.get("account", "default"))

    engine: ForwardTraceEngine | ReverseTraceEngine
    try:
        if scenario_id in _FORWARD_SCENARIOS:
            engine = await _get_forward_engine()
        else:
            engine = await _get_reverse_engine()

        result = await engine.trace(trace_request, account)
        return {"code": 200, "data": result.model_dump()}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Scenario trace failed: %s", scenario_id)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/nl-parse")
async def nl_parse(req: NLParseRequest) -> dict[str, Any]:
    try:
        result = await handle_nl_parse(req.text)
        return {"code": 200, "data": result}
    except Exception as e:
        logger.exception("NL parse failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/report/save")
async def save_report(req: ReportSaveRequest) -> dict[str, Any]:
    try:
        scenario = _validate_scenario(req.scenario)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid scenario: {e}") from e

    report = Report(
        name=req.name,
        scenario=scenario,
        entry_table=req.entry_table,
        entry_batch=req.entry_batch,
        trace_result=TraceResult(**req.trace_result) if req.trace_result else None,
        summary=TraceSummary(**req.summary) if req.summary else TraceSummary(),
        tags=req.tags,
        created_by=req.created_by,
    )

    try:
        key = await _report_store.save_report(report)
        return {"code": 200, "data": {"key": key}}
    except Exception as e:
        logger.exception("Save report failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/report/{report_id}")
async def get_report(report_id: str) -> dict[str, Any]:
    try:
        report = await _report_store.get_report(report_id)
        if report is None:
            raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")
        return {"code": 200, "data": report.model_dump()}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Get report failed: %s", report_id)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/reports")
async def list_reports(
    scenario: str = Query(default="", description="Filter by scenario name"),
    page: int = Query(default=1, ge=1, description="Page number"),
    limit: int = Query(default=20, ge=1, le=100, description="Items per page"),
) -> dict[str, Any]:
    try:
        scenario_param: Optional[str] = scenario if scenario else None
        reports = await _report_store.list_reports(
            scenario=scenario_param, page=page, limit=limit
        )
        return {
            "code": 200,
            "data": [r.model_dump() for r in reports],
            "page": page,
            "limit": limit,
        }
    except Exception as e:
        logger.exception("List reports failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/report/{report_id}")
async def delete_report(report_id: str) -> dict[str, Any]:
    try:
        deleted = await _report_store.delete_report(report_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")
        return {"code": 200, "message": f"Report '{report_id}' deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Delete report failed: %s", report_id)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "trace-engine"}
