"""
NL→SQL Pipeline - Pydantic Models

Defines all data models for the NL→SQL pipeline:
PipelineConfig, PipelineResult, IntentMatch, QueryPlan,
SchemaContext, SQLResult, ValidationResult.

# Last Update: 2026-03-24 19:27:14
# Author: Daniel Chung
# Version: 1.2.0
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class GenerationStrategy(str, Enum):
    """SQL generation strategy tier."""

    TEMPLATE = "template"
    SMALL_LLM = "small_llm"
    LARGE_LLM = "large_llm"


class PipelineConfig(BaseModel):
    """Configuration for the NL→SQL pipeline."""

    ollama_base_url: str = Field(default="http://localhost:11434")
    small_model: str = Field(default="mistral-nemo:12b")
    large_model: str = Field(default="qwen3-coder:30b")
    embedding_model: str = Field(default="bge-m3:latest")
    qdrant_url: str = Field(default="http://localhost:6333")
    qdrant_collection: str = Field(default="data_agent_intents")
    arango_url: str = Field(default="http://localhost:8529")
    arango_db: str = Field(default="abc_desktop")
    arango_user: str = Field(default="root")
    arango_password: str = Field(default="abc_desktop_2026")
    s3_endpoint: str = Field(default="http://localhost:8334")
    s3_bucket: str = Field(default="sap")
    s3_access_key: str = Field(default="")
    s3_secret_key: str = Field(default="")
    match_threshold: float = Field(default=0.58)
    max_retries: int = Field(default=1)
    generate_timeout: float = Field(default=60.0)


class IntentMatch(BaseModel):
    """Result of intent classification from Qdrant."""

    intent_id: str
    score: float
    generation_strategy: GenerationStrategy = GenerationStrategy.TEMPLATE
    sql_template: str = ""
    tables: list[str] = Field(default_factory=list)
    core_fields: list[str] = Field(default_factory=list)
    description: str = ""
    intent_type: str = ""
    group: str = ""
    nl_examples: list[str] = Field(default_factory=list)
    example_sqls: list[str] = Field(default_factory=list)


class TableSchema(BaseModel):
    """Schema metadata for a single table."""

    table_name: str
    description: str = ""
    row_count: int = 0
    module: str = ""
    tab: str = ""
    sheet_key: str = ""
    s3_path: str = ""


class FieldSchema(BaseModel):
    """Schema metadata for a single field."""

    table_name: str
    field_name: str
    data_type: str = ""
    description: str = ""
    is_key: bool = False
    field_id: str = ""
    writable: bool = True
    is_subtable_field: bool = False
    subtable_key: str = ""


class TableRelation(BaseModel):
    """Relationship between two tables."""

    from_table: str
    from_field: str
    to_table: str
    to_field: str
    relation_type: str = "INNER"


class JoinPath(BaseModel):
    """A single join path step."""

    target_table: str
    from_field: str
    to_field: str
    join_type: str = "INNER"


class SchemaContext(BaseModel):
    """Pruned schema context for LLM consumption."""

    tables: list[TableSchema] = Field(default_factory=list)
    fields: list[FieldSchema] = Field(default_factory=list)
    relations: list[TableRelation] = Field(default_factory=list)
    join_graph: dict[str, list[JoinPath]] = Field(default_factory=dict)


class QueryPlanFilter(BaseModel):
    """A filter condition in the query plan."""

    field: str
    operator: str = "="
    value: str = ""


class QueryPlanJoin(BaseModel):
    """A join specification in the query plan."""

    from_ref: str  # e.g. "EKKO.EBELN"
    to_ref: str  # e.g. "EKPO.EBELN"
    join_type: str = "INNER"


class QueryPlanOrderBy(BaseModel):
    """An ordering specification in the query plan."""

    field: str
    direction: str = "ASC"


class QueryPlan(BaseModel):
    """JSON Query Plan - intermediate representation between NL and SQL."""

    intent_type: str = ""
    primary_table: str = ""
    tables: list[str] = Field(default_factory=list)
    joins: list[QueryPlanJoin] = Field(default_factory=list)
    filters: list[QueryPlanFilter] = Field(default_factory=list)
    select_fields: list[str] = Field(default_factory=list)
    aggregations: list[str] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    order_by: list[QueryPlanOrderBy] = Field(default_factory=list)
    limit: int = 100


class ValidationError(BaseModel):
    """A single validation error."""

    layer: int  # 1=regex, 2=AST, 3=LLM semantic
    message: str
    severity: str = "error"  # error, warning


class ValidationResult(BaseModel):
    """Result of SQL validation."""

    is_valid: bool
    errors: list[ValidationError] = Field(default_factory=list)
    warnings: list[ValidationError] = Field(default_factory=list)


class SQLResult(BaseModel):
    """Result of SQL execution."""

    sql: str
    rows: list[dict[str, object]] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)
    row_count: int = 0
    execution_time_ms: float = 0.0


class PipelinePhaseResult(BaseModel):
    """Timing for a single pipeline phase."""

    phase: str
    duration_ms: float
    success: bool = True
    error: Optional[str] = None


class PipelineResult(BaseModel):
    """Final result of the NL→SQL pipeline."""

    success: bool
    query: str
    matched_intent: Optional[IntentMatch] = None
    query_plan: Optional[QueryPlan] = None
    generated_sql: str = ""
    validation: Optional[ValidationResult] = None
    execution_result: Optional[SQLResult] = None
    clarification: Optional["ClarificationResponse"] = None
    error_explanation: Optional["ErrorExplanation"] = None
    error: Optional[str] = None
    phases: list[PipelinePhaseResult] = Field(default_factory=list)
    total_time_ms: float = 0.0


class ClarificationQuestion(BaseModel):
    """A single clarification question for an ambiguous NL query."""

    field: str = ""
    question: str


class ClarificationResponse(BaseModel):
    """Pre-query clarification when NL query is semantically incomplete."""

    needs_clarification: bool
    reason: str = ""
    questions: list[ClarificationQuestion] = Field(default_factory=list)


class ErrorExplanation(BaseModel):
    """Post-query error explanation when pipeline fails."""

    error_type: str
    explanation: str
    suggestions: list[str] = Field(default_factory=list)
