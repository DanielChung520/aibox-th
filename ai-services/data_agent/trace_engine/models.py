"""
@file        models.py
@description Pydantic data models for the Trace Engine.
             Defines data structures for scenarios, nodes, edges, results, and reports.
@lastUpdate  2026-05-17
@author      Daniel Chung
@version     1.0.0
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TraceScenario(str, Enum):
    """Supported data-trace scenarios."""

    SHIPMENT_BATCH = "shipment_batch"
    INCOMING_BATCH = "incoming_batch"
    PRODUCT_FULL_HISTORY = "product_full_history"
    WORK_ORDER = "work_order"
    COMPLAINT_RECALL = "complaint_recall"
    EXPIRY_TRACKING = "expiry_tracking"
    QUALITY_ISSUE = "quality_issue"
    SUPPLIER_TRACE = "supplier_trace"


class TraceNode(BaseModel):
    """A single record node in the trace graph."""

    table_key: str
    table_name: str
    ragic_id: str
    fields: dict[str, object] = Field(default_factory=dict)
    depth: int = 0


class TraceEdge(BaseModel):
    """A directed edge connecting two trace nodes."""

    from_ragic_id: str
    from_table_key: str
    to_ragic_id: str
    to_table_key: str
    via_field_id: str = ""
    via_field_name: str = ""
    relation_type: str = "link"


class ImpactMetrics(BaseModel):
    """Aggregated impact counts from a trace result."""

    customer_count: int = 0
    batch_count: int = 0
    product_count: int = 0
    supplier_count: int = 0


class TraceSummary(BaseModel):
    """Summary statistics for a trace operation."""

    node_count: int = 0
    edge_count: int = 0
    max_depth: int = 0
    total_time_ms: float = 0.0
    has_results: bool = False
    has_more: bool = False
    impact_metrics: Optional[ImpactMetrics] = None


class TraceError(BaseModel):
    """Non-fatal error encountered during a trace hop."""

    hop: str = ""
    error: str = ""
    partial: bool = True


class TraceResult(BaseModel):
    """Complete output of a single trace operation."""

    scenario: TraceScenario
    nodes: list[TraceNode] = Field(default_factory=list)
    edges: list[TraceEdge] = Field(default_factory=list)
    summary: TraceSummary = Field(default_factory=TraceSummary)
    errors: list[TraceError] = Field(default_factory=list)


class ScenarioDefinition(BaseModel):
    """Metadata describing a trace scenario's configuration."""

    id: TraceScenario
    name: str
    description: str
    entry_tables: list[str] = Field(default_factory=list)
    batch_field_ids: list[str] = Field(default_factory=list)
    default_depth: int = 3
    direction: str = "bidirectional"


class Report(BaseModel):
    """A persisted trace report document."""

    id: str = ""
    name: str
    scenario: TraceScenario
    entry_table: str = ""
    entry_batch: str = ""
    trace_result: Optional[TraceResult] = None
    summary: TraceSummary = Field(default_factory=TraceSummary)
    tags: list[str] = Field(default_factory=list)
    created_by: str = ""
    created_at: str = ""
    updated_at: str = ""


class TraceRequest(BaseModel):
    """Parameters to initiate a trace operation."""

    scenario: TraceScenario
    entry_table: str = ""
    entry_batch: str = ""
    depth: int = Field(default=3, ge=1, le=5)
    max_fan_out: int = Field(default=50, ge=1, le=200)
    options: dict[str, object] = Field(default_factory=dict)
