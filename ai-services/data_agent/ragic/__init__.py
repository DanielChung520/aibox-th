"""
RagicDataAgent - Natural Language to Ragic API query translator.

Reads data directly from Ragic Cloud API (zero local sync).
Schema and Intents stored in Qdrant for vector retrieval.

# Last Update: 2026-04-13 02:46:54
# Author: Daniel Chung
# Version: 1.7.0

Modules:
    client              - RagicAPIClient (HTTP GET, rate-limit, pagination)
    exceptions          - RagicError hierarchy (Auth/Forbidden/NotFound/RateLimit/Timeout)
    models              - Pydantic data models (connection, query, NL, schema, intent)
    models_phase9       - Phase 9-11 models (parsing, graph, orchestrator)
    schema_store        - Qdrant-backed schema storage (embed + search)
    schema_converter    - ParsedTable → RagicTableSchema conversion
    intent_store        - Qdrant-backed intent storage (embed + search)
    intent_generator    - Auto-generate intents (3 actions × 3 languages)
    nl_parser           - NL → Intent match → parameter translation
    query_engine        - Execute queries with field-label resolution
    query_router        - Path A/B routing (tool-calling / pandas)
    tool_calling_engine - Ollama JSON Schema constrained generation (Path A)
    schema_linker       - Intent → table → field schema → enum constraint
    aggregation_builder - LLM constrained generation for aggregation plans (Path B)
    pandas_engine       - Pandas-based local aggregation engine (Path B)
    formatter           - Multi-format output (CSV with BOM, Excel)
    config_loader       - Multi-tenant config from Ragic system module
    schema_sync         - Auto-sync table schemas from Ragic API
    md_parser           - Parse Ragic schema definitions from Markdown
    arango_writer       - Write schemas/fields/relations to ArangoDB
    import_orchestrator - End-to-end MD import pipeline
    step_executor       - Single-step Ragic query with timeout
    result_merger       - Merge multi-step query results
    multi_step_orchestrator - N-step chained query pipeline
    router              - FastAPI endpoints
"""

from data_agent.ragic.aggregation_builder import AggregationPlan, AggregationResult
from data_agent.ragic.arango_writer import RagicArangoWriter
from data_agent.ragic.client import RagicAPIClient
from data_agent.ragic.config_loader import RagicConfigLoader
from data_agent.ragic.formatter import to_csv_bytes, to_excel_bytes
from data_agent.ragic.graph_query import RagicGraphQuery
from data_agent.ragic.import_orchestrator import RagicImportOrchestrator
from data_agent.ragic.intent_generator import IntentGenerator
from data_agent.ragic.intent_store import IntentVectorStore
from data_agent.ragic.md_parser import RagicMDParser
from data_agent.ragic.md_parser_relations import RelationExtractor
from data_agent.ragic.models_phase9 import (
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
from data_agent.ragic.multi_step_orchestrator import MultiStepOrchestrator
from data_agent.ragic.nl_parser import RagicNLParser
from data_agent.ragic.pandas_engine import PandasEngineResult
from data_agent.ragic.query_engine import RagicQueryEngine
from data_agent.ragic.query_router import RouteDecision
from data_agent.ragic.result_merger import ResultMerger
from data_agent.ragic.schema_linker import LinkedSchema
from data_agent.ragic.schema_store import RagicSchemaStore
from data_agent.ragic.schema_sync import RagicSchemaSync
from data_agent.ragic.step_executor import RagicStepExecutor
from data_agent.ragic.tool_calling_engine import ToolCallingResult

__all__ = [
    "AggregationPlan",
    "AggregationResult",
    "RagicAPIClient",
    "RagicArangoWriter",
    "RagicConfigLoader",
    "RagicGraphQuery",
    "RagicImportOrchestrator",
    "IntentVectorStore",
    "RagicMDParser",
    "RagicNLParser",
    "RagicQueryEngine",
    "RagicSchemaStore",
    "RagicSchemaSync",
    "RagicStepExecutor",
    "IntentGenerator",
    "MultiStepOrchestrator",
    "RelationExtractor",
    "ResultMerger",
    "PandasEngineResult",
    "to_csv_bytes",
    "to_excel_bytes",
    "LinkedFieldRef",
    "LoadedFieldRef",
    "ParsedField",
    "ParsedTable",
    "TableRelationEdge",
    "GraphRelation",
    "GraphQueryResult",
    "ImportResult",
    "StepResult",
    "MultiStepQuery",
    "MultiStepResult",
    "RouteDecision",
    "LinkedSchema",
    "ToolCallingResult",
]
