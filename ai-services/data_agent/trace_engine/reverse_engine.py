"""
@file        reverse_engine.py
@description Reverse/impact trace engines for scenarios 5-8.
@lastUpdate  2026-05-17
"""
import logging
import time

from data_agent.trace_engine.base_engine import BaseTraceEngine
from data_agent.trace_engine.models import (
    TraceRequest,
    TraceResult,
    TraceScenario,
    TraceNode,
    TraceEdge,
    TraceSummary,
    TraceError,
    ImpactMetrics,
)
from data_agent.ragic.record_tracer import RecordTracer
from data_agent.ragic.config_loader import RagicConfigLoader

logger = logging.getLogger(__name__)


class ReverseTraceEngine(BaseTraceEngine):
    """Reverse/impact trace: find upstream sources, compute impact metrics."""

    def __init__(self, tracer: RecordTracer, config_loader: RagicConfigLoader) -> None:
        super().__init__(tracer, config_loader)

    async def trace(self, request: TraceRequest, account: str) -> TraceResult:
        start = time.monotonic()
        try:
            match request.scenario:
                case TraceScenario.COMPLAINT_RECALL:
                    result = await self._trace_complaint_recall(request, account)
                case TraceScenario.EXPIRY_TRACKING:
                    result = await self._trace_expiry(request, account)
                case TraceScenario.QUALITY_ISSUE:
                    result = await self._trace(request, account)
                case TraceScenario.SUPPLIER_TRACE:
                    result = await self._trace_supplier(request, account)
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

    async def _trace(self, request: TraceRequest, account: str) -> TraceResult:
        """Generic reverse trace using RecordTracer."""
        batch_no = request.entry_batch.strip().lower() if request.entry_batch else ""
        entry_table = request.entry_table or ""
        all_nodes: list[TraceNode] = []
        all_edges: list[TraceEdge] = []
        errors: list[TraceError] = []

        tables_to_try = [entry_table] if entry_table else []
        if not tables_to_try:
            for bf in self._config.batch_fields:
                tables_to_try.append(bf.table_key)
            tables_to_try = list(dict.fromkeys(tables_to_try))[:3]

        for table_key in tables_to_try:
            try:
                graph = await self._tracer.trace(
                    table_key=table_key, record_id=batch_no,
                    account=account, depth=request.depth,
                    max_fan_out=request.max_fan_out,
                )
                for n in graph.nodes:
                    all_nodes.append(TraceNode(
                        table_key=n.table_key, table_name=n.table_name,
                        ragic_id=n.ragic_id, fields=n.fields, depth=n.depth,
                    ))
                for e in graph.edges:
                    all_edges.append(TraceEdge(
                        from_ragic_id=e.from_ragic_id,
                        from_table_key=e.from_table_key,
                        to_ragic_id=e.to_ragic_id, to_table_key=e.to_table_key,
                        via_field_id=e.via_field_id, via_field_name=e.via_field_name,
                        relation_type=e.relation_type,
                    ))
            except Exception as exc:
                errors.append(TraceError(hop=table_key, error=str(exc), partial=True))

        has_results = len(all_nodes) > 0
        return TraceResult(
            scenario=request.scenario, nodes=all_nodes, edges=all_edges,
            errors=errors,
            summary=TraceSummary(
                node_count=len(all_nodes), edge_count=len(all_edges),
                max_depth=max(n.depth for n in all_nodes) if all_nodes else 0,
                has_results=has_results,
            ),
        )

    async def _trace_complaint_recall(self, request: TraceRequest, account: str) -> TraceResult:
        """Complaint recall: forward to customers + backward to raw materials + lateral impact."""
        result = await self._trace(request, account)
        # Compute impact metrics
        customer_count = 0
        batch_count = 0
        product_count = 0
        supplier_count = 0
        for n in result.nodes:
            f = n.fields
            if any("客戶" in k or "customer" in k.lower() for k in f):
                customer_count += 1
            if any("批號" in k or "batch" in k.lower() for k in f):
                batch_count += 1
            if any("品名" in k or "product" in k.lower() or "成品" in k for k in f):
                product_count += 1
            if any("供應商" in k or "supplier" in k.lower() for k in f):
                supplier_count += 1
        result.summary.impact_metrics = ImpactMetrics(
            customer_count=customer_count,
            batch_count=batch_count,
            product_count=product_count,
            supplier_count=supplier_count,
        )
        return result

    async def _trace_expiry(self, request: TraceRequest, account: str) -> TraceResult:
        """Expiry tracking: find near-expiry batches by date range."""
        from_date = str(request.options.get("from_date", ""))
        to_date = str(request.options.get("to_date", ""))
        result = await self._trace(request, account)
        # Filter nodes by date fields if dates provided
        if from_date or to_date:
            filtered_nodes: list[TraceNode] = []
            for n in result.nodes:
                for _k, v in n.fields.items():
                    vs = str(v)
                    if from_date and vs < from_date:
                        continue
                    if to_date and vs > to_date:
                        continue
                filtered_nodes.append(n)
            result.nodes = filtered_nodes
            result.summary.node_count = len(filtered_nodes)
        return result

    async def _trace_supplier(self, request: TraceRequest, account: str) -> TraceResult:
        """Supplier trace: supplier code - incoming batches - finished goods."""
        return await self._trace(request, account)
