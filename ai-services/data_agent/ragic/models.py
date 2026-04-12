"""
@file        models.py
@description Pydantic models for RagicDataAgent — API client, Schema, Intent, NL Parser, and QueryEngine types.
             Phase 9-11 models are in models_phase9.py and re-exported here.
@lastUpdate  2026-04-12 08:50:59
@author      Daniel Chung
@version     1.7.0
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RagicOperator(str, Enum):
    """Ragic where-clause operators."""

    EQ = "eq"
    LIKE = "like"
    GTE = "gte"
    LTE = "lte"
    GT = "gt"
    LT = "lt"
    REGEX = "regex"


class RagicSortDirection(str, Enum):
    """Sort direction for Ragic order parameter."""

    ASC = "ASC"
    DESC = "DESC"


class RagicWhereClause(BaseModel):
    """Single where filter for Ragic API."""

    field_id: str
    operator: RagicOperator
    value: str


class RagicQueryParams(BaseModel):
    """Parameters to build a Ragic API GET request."""

    where: list[RagicWhereClause] = Field(default_factory=list)
    limit: int = Field(default=1000, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
    order_field: Optional[str] = None
    order_direction: RagicSortDirection = RagicSortDirection.DESC
    naming: str = Field(default="EID")
    subtables: Optional[int] = None
    info: bool = False


class RagicConnectionConfig(BaseModel):
    """Configuration for a single Ragic account connection."""

    account: str
    api_key: str
    server_prefix: str = "ap15"
    enabled: bool = True
    description: str = ""

    @property
    def base_url(self) -> str:
        return f"https://{self.server_prefix}.ragic.com"


class RagicRecord(BaseModel):
    """A single Ragic record (row)."""

    ragic_id: str
    fields: dict[str, object] = Field(default_factory=dict)


class RagicPagination(BaseModel):
    """Pagination metadata."""

    offset: int = 0
    limit: int = 1000
    returned_count: int = 0
    has_more: bool = False


class RagicQueryResult(BaseModel):
    """Result of a Ragic API query."""

    records: list[RagicRecord] = Field(default_factory=list)
    record_count: int = 0
    pagination: RagicPagination = Field(default_factory=RagicPagination)
    execution_time_ms: float = 0.0
    connection: str = ""
    table_key: str = ""
    raw_url: str = ""


# ---------------------------------------------------------------------------
# Phase 2: Schema Store models
# ---------------------------------------------------------------------------


class RagicFieldSchema(BaseModel):
    """Schema of a single field within a Ragic sheet."""

    name: str
    field_type: str = "text"
    options: list[str] = Field(default_factory=list)
    description: str = ""
    business_aliases: list[str] = Field(default_factory=list)
    writable: bool = True
    is_subtable_field: bool = False
    subtable_key: str = ""


class RagicTableSchema(BaseModel):
    """Full schema for one Ragic sheet, stored as Qdrant point payload."""

    account: str
    table_key: str
    table_name: str
    tab_path: str = ""
    sheet_index: int = 0
    description: str = ""
    module: str = ""
    version: str = ""
    fields: dict[str, RagicFieldSchema] = Field(default_factory=dict)
    subtables: dict[str, str] = Field(default_factory=dict)

    @property
    def point_id_seed(self) -> str:
        return f"{self.account}_{self.table_key.replace('/', '_')}"


class SchemaUpsertRequest(BaseModel):
    """Request to upsert one or more schemas into Qdrant."""

    schemas: list[RagicTableSchema]


class SchemaSearchRequest(BaseModel):
    """Search schemas by natural language query."""

    query: str
    account: Optional[str] = None
    top_k: int = Field(default=5, ge=1, le=20)


class SchemaSearchResult(BaseModel):
    """Single schema search hit."""

    table_key: str
    table_name: str
    account: str
    score: float
    schema_data: RagicTableSchema


class SchemaSearchResponse(BaseModel):
    """Response for schema search."""

    query: str
    results: list[SchemaSearchResult] = Field(default_factory=list)
    total: int = 0


# ---------------------------------------------------------------------------
# Phase 3: Intent Store models
# ---------------------------------------------------------------------------


class RagicFilterTemplate(BaseModel):
    """Pre-configured filter for an Intent."""

    field_id: str
    operator: RagicOperator
    value: str


class RagicIntent(BaseModel):
    """A single intent stored in Qdrant for NL → Ragic API matching."""

    account: str
    intent_id: str
    nl_patterns: list[str] = Field(default_factory=list)
    description: str = ""
    action: str = "list"
    table_key: str = ""
    filter_template: Optional[RagicFilterTemplate] = None
    api_template: str = ""

    @property
    def point_id_seed(self) -> str:
        return f"{self.account}_intent_{self.intent_id}"


class IntentUpsertRequest(BaseModel):
    """Request to upsert one or more intents into Qdrant."""

    intents: list[RagicIntent]


class IntentSearchRequest(BaseModel):
    """Search intents by natural language query."""

    query: str
    account: Optional[str] = None
    top_k: int = Field(default=5, ge=1, le=20)


class IntentSearchResult(BaseModel):
    """Single intent search hit."""

    intent_id: str
    account: str
    score: float
    intent_data: RagicIntent


class IntentSearchResponse(BaseModel):
    """Response for intent search."""

    query: str
    results: list[IntentSearchResult] = Field(default_factory=list)
    total: int = 0
    best_match: Optional[IntentSearchResult] = None


# ---------------------------------------------------------------------------
# Phase 4: NL Parser models
# ---------------------------------------------------------------------------


class NLQueryOptions(BaseModel):
    include_subtables: bool = False
    limit: int = Field(default=1000, ge=1, le=1000)
    auto_paginate: bool = False


class NLQueryRequest(BaseModel):
    """POST /ragic/query request body."""

    query: str
    connection_name: Optional[str] = None
    table_key: Optional[str] = None
    output_format: str = "json"
    options: NLQueryOptions = Field(default_factory=NLQueryOptions)


class MatchedIntentInfo(BaseModel):
    intent_id: str
    score: float
    action: str = ""
    table_key: str = ""


class TranslatedParams(BaseModel):
    where: list[RagicWhereClause] = Field(default_factory=list)
    limit: int = 1000
    offset: int = 0
    naming: str = "EID"
    order_field: Optional[str] = None
    order_direction: str = "DESC"


class NLQueryResponse(BaseModel):
    """POST /ragic/query — standard response protocol."""

    code: int = 0
    status: str = "success"
    clarification: Optional["NLClarification"] = None
    result: Optional["NLResultSet"] = None
    intent: Optional["NLIntentMatch"] = None
    post_error: Optional["NLPostError"] = None
    metadata: Optional["NLQueryMetadata"] = None


class NLClarification(BaseModel):
    message: str
    suggestions: list[str] = Field(default_factory=list)


class NLResultSet(BaseModel):
    records: list[RagicRecord] = Field(default_factory=list)
    record_count: int = 0
    pagination: RagicPagination = Field(default_factory=RagicPagination)
    field_labels: dict[str, str] = Field(default_factory=dict)
    execution_time_ms: float = 0.0
    stats: Optional["NLResultStats"] = None


class NLResultStats(BaseModel):
    total_fields: int = 0
    estimated_tokens: int = 0


class NLIntentMatch(BaseModel):
    intent_id: str
    score: float
    confidence: str = ""
    action: str = ""
    table_key: str = ""


class NLPostError(BaseModel):
    error_code: int = 0
    raw_error: str = ""
    message: str = ""


class NLQueryData(BaseModel):
    query: str
    intent_matched: Optional[MatchedIntentInfo] = None
    translated_params: Optional[TranslatedParams] = None
    records: list[RagicRecord] = Field(default_factory=list)
    record_count: int = 0
    pagination: RagicPagination = Field(default_factory=RagicPagination)
    execution_time_ms: float = 0.0
    field_labels: dict[str, str] = Field(default_factory=dict)


class NLQueryMetadata(BaseModel):
    connection: str = ""
    table_key: str = ""
    output_format: str = "json"
    query: str = ""
    translated_params: Optional[TranslatedParams] = None


# ---------------------------------------------------------------------------
# Phase 5: QueryEngine models
# ---------------------------------------------------------------------------


class FormattedRecord(BaseModel):
    ragic_id: str
    fields: dict[str, object] = Field(default_factory=dict)
    field_labels: dict[str, str] = Field(default_factory=dict)


class QueryEngineResult(BaseModel):
    records: list[FormattedRecord] = Field(default_factory=list)
    record_count: int = 0
    total_pages: int = 1
    current_page: int = 1
    page_size: int = 1000
    has_more: bool = False
    execution_time_ms: float = 0.0
    table_key: str = ""
    connection: str = ""


# ---------------------------------------------------------------------------
# Phase 9-11: Re-export from models_phase9.py
# ---------------------------------------------------------------------------

from data_agent.ragic.models_phase9 import (  # noqa: E402, F401
    GraphQueryResult,
    GraphRelation,
    ImportResult,
    LinkedFieldRef,
    LoadedFieldRef,
    MultiStepQuery,
    MultiStepResult,
    ParsedField,
    ParsedTable,
    StepResult,
    TableRelationEdge,
)
