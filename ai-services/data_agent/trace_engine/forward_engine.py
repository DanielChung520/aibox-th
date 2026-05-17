"""
@file        forward_engine.py
@description Forward (downstream) trace engines for scenarios 1-4.
@lastUpdate  2026-05-17
"""
import logging
import time
from typing import Any

from data_agent.trace_engine.base_engine import BaseTraceEngine
from data_agent.trace_engine.models import (
    TraceRequest,
    TraceResult,
    TraceScenario,
    TraceNode,
    TraceEdge,
    TraceSummary,
    TraceError,
)
from data_agent.ragic.record_tracer import RecordTracer
from data_agent.ragic.config_loader import RagicConfigLoader

logger = logging.getLogger(__name__)


class ForwardTraceEngine(BaseTraceEngine):
    """Forward/downstream trace: entry record - trace FK - collect relations."""

    def __init__(self, tracer: RecordTracer, config_loader: RagicConfigLoader) -> None:
        super().__init__(tracer, config_loader)

    async def trace(self, request: TraceRequest, account: str) -> TraceResult:
        start = time.monotonic()
        try:
            match request.scenario:
                case TraceScenario.SHIPMENT_BATCH:
                    result = await self._trace(request, account)
                case TraceScenario.INCOMING_BATCH:
                    result = await self._trace(request, account)
                case TraceScenario.PRODUCT_FULL_HISTORY:
                    result = await self._trace(request, account, depth=max(request.depth, 5))
                case TraceScenario.WORK_ORDER:
                    result = await self._trace(request, account)
                case _:
                    result = TraceResult(
                        scenario=request.scenario,
                        summary=TraceSummary(has_results=False),
                    )
            result.summary.total_time_ms = (time.monotonic() - start) * 1000
            return result
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            return TraceResult(
                scenario=request.scenario,
                errors=[TraceError(hop="trace", error=str(e), partial=False)],
                summary=TraceSummary(has_results=False, total_time_ms=elapsed),
            )

    async def _trace(
        self,
        request: TraceRequest,
        account: str,
        depth: int | None = None,
    ) -> TraceResult:
        """Generic forward trace using RecordTracer."""
        batch_no = request.entry_batch.strip().lower() if request.entry_batch else ""
        entry_table = request.entry_table or ""

        # Try each configured entry table
        all_nodes: list[TraceNode] = []
        all_edges: list[TraceEdge] = []
        errors: list[TraceError] = []
        max_depth = depth or request.depth

        tables_to_try = [entry_table] if entry_table else []
        if not tables_to_try:
            # Use scenario config
            for bf in self._config.batch_fields:
                tables_to_try.append(bf.table_key)
            tables_to_try = list(dict.fromkeys(tables_to_try))[:3]

        for table_key in tables_to_try:
            try:
                graph = await self._tracer.trace(
                    table_key=table_key,
                    record_id=batch_no,
                    account=account,
                    depth=max_depth,
                    max_fan_out=request.max_fan_out,
                )
                for n in graph.nodes:
                    all_nodes.append(TraceNode(
                        table_key=n.table_key,
                        table_name=n.table_name,
                        ragic_id=n.ragic_id,
                        fields=n.fields,
                        depth=n.depth,
                    ))
                for e in graph.edges:
                    all_edges.append(TraceEdge(
                        from_ragic_id=e.from_ragic_id,
                        from_table_key=e.from_table_key,
                        to_ragic_id=e.to_ragic_id,
                        to_table_key=e.to_table_key,
                        via_field_id=e.via_field_id,
                        via_field_name=e.via_field_name,
                        relation_type=e.relation_type,
                    ))
            except Exception as exc:
                errors.append(TraceError(hop=table_key, error=str(exc), partial=True))

        has_results = len(all_nodes) > 0
        return TraceResult(
            scenario=request.scenario,
            nodes=all_nodes,
            edges=all_edges,
            errors=errors,
            summary=TraceSummary(
                node_count=len(all_nodes),
                edge_count=len(all_edges),
                max_depth=max(n.depth for n in all_nodes) if all_nodes else 0,
                has_results=has_results,
            ),
        )
