"""
@file        models_phase9.py
@description Phase 9-11 Pydantic models — MD parsing, graph relations,
             multi-step orchestration, and import results.
@lastUpdate  2026-04-11 16:58:26
@author      Daniel Chung
@version     1.0.0
"""

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Phase 9: MD Parser models
# ---------------------------------------------------------------------------


class LinkedFieldRef(BaseModel):
    """Reference parsed from '連結到<form>表單上的<field>' memo."""

    target_form: str
    target_field: str


class LoadedFieldRef(BaseModel):
    """Reference parsed from '從<form>表單上的<field>載入欄位值' memo."""

    source_form: str
    source_field: str
    sync_mode: str = ""


class ParsedField(BaseModel):
    """A single field row parsed from the MD pipe table."""

    name: str
    field_id: str
    field_type: str
    writable: bool
    write_format: str = ""
    memo: str = ""
    linked_to: LinkedFieldRef | None = None
    loaded_from: LoadedFieldRef | None = None


class ParsedTable(BaseModel):
    """One Ragic table (sheet) parsed from the MD document."""

    table_name: str
    form_url: str = ""
    api_url: str = ""
    main_form_key: str = ""
    tab_path: str = ""
    sheet_index: int = 0
    tab_name: str = ""
    account: str = ""
    fields: list[ParsedField] = Field(default_factory=list)
    subtables: dict[str, list[ParsedField]] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Phase 10: Knowledge Graph models
# ---------------------------------------------------------------------------


class TableRelationEdge(BaseModel):
    """A single directed edge between two tables (link or load)."""

    from_table: str
    from_field: str
    from_field_id: str = ""
    to_table: str
    to_field: str
    relation_type: str = "link"
    sync_mode: str | None = None


class GraphRelation(BaseModel):
    """One relation in a graph query result."""

    target_table: str
    target_field: str
    source_field: str
    source_field_id: str = ""
    relation_type: str = "link"
    direction: str = "outgoing"


class GraphQueryResult(BaseModel):
    """Result of a graph traversal query for a table."""

    table: str
    relations: list[GraphRelation] = Field(default_factory=list)
    depth: int = 1


# ---------------------------------------------------------------------------
# Phase 9: Import result model
# ---------------------------------------------------------------------------


class ImportResult(BaseModel):
    """Result summary of a bulk MD import operation."""

    account: str
    tables_parsed: int = 0
    schemas_vectorized: int = 0
    intents_generated: int = 0
    relations_extracted: int = 0
    arango_tables_written: int = 0
    arango_fields_written: int = 0
    arango_relations_written: int = 0
    errors: list[str] = Field(default_factory=list)
    duration_ms: float = 0.0


# ---------------------------------------------------------------------------
# Phase 11: Multi-Step Orchestrator models
# ---------------------------------------------------------------------------


class StepResult(BaseModel):
    """Result of a single step in a multi-step query pipeline."""

    step_index: int
    table_key: str = ""
    table_name: str = ""
    query_params: dict[str, object] = Field(default_factory=dict)
    records: list[dict[str, object]] = Field(default_factory=list)
    record_count: int = 0
    execution_time_ms: float = 0.0
    error: str | None = None


class MultiStepQuery(BaseModel):
    """Request body for a multi-step chained query."""

    query: str
    account: str = ""
    max_steps: int = Field(default=3, ge=1, le=10)
    max_fan_out: int = Field(default=10, ge=1, le=50)
    step_timeout_s: float = Field(default=15.0, gt=0)
    total_timeout_s: float = Field(default=60.0, gt=0)


class MultiStepResult(BaseModel):
    """Result of a multi-step chained query."""

    query: str
    steps: list[StepResult] = Field(default_factory=list)
    merged_records: list[dict[str, object]] = Field(default_factory=list)
    total_steps: int = 0
    total_records: int = 0
    total_time_ms: float = 0.0
    partial_failure: bool = False
    errors: list[str] = Field(default_factory=list)
