/**
 * @file        Data Agent API 服務層 - 型別定義
 * @description DA 的 Schema、Intents、Query 等型別介面定義
 * @lastUpdate  2026-05-01 10:31:57
 * @author      Daniel Chung
 */

export interface LinkedFieldRef {
  target_form: string;
  target_field: string;
}

export interface LoadedFieldRef {
  source_form: string;
  source_field: string;
  sync_mode: string;
}

export interface TableInfo {
  table_id: string;
  table_name: string;
  module: string;
  tab: string;
  tab_name: string;
  sheet_key: string;
  sheet_number: string;
  sheet_url: string;
  api_url: string;
  data_source: 'ragic' | 'sap';
  status: 'enabled' | 'disabled' | 'deprecated';
  created_at: string;
  updated_at: string;
  updated_by: string;
  preview_mode?: 'paged' | 'all';
}

export interface FieldInfo {
  table_id: string;
  field_id: string;
  field_name: string;
  field_type: string;
  writable: boolean;
  writable_raw: string;
  write_format: string;
  memo: string;
  linked_to?: LinkedFieldRef | null;
  loaded_from?: LoadedFieldRef | null;
  status: string;
}

export interface TableRelation {
  relation_id: string;
  left_table: string;
  left_field: string;
  right_table: string;
  right_field: string;
  join_type: 'INNER' | 'LEFT';
  cardinality: '1:1' | '1:N' | 'N:1' | 'N:N';
  confidence: number;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface QueryRequest {
  query: string;
  session_id?: string;
  user_id?: string;
  options?: {
    timezone?: string;
    limit?: number;
    module_scope?: string[];
    return_debug?: boolean;
  };
}

export interface IntentSummary {
  intent_type: string;
  confidence: number;
}

export interface QueryResponse {
  code: number;
  message?: string;
  data: {
    sql: string;
    results: Record<string, unknown>[];
    columns?: string[];
    metadata: {
      duration_ms: number;
      row_count: number;
      truncated: boolean;
      trace_id: string;
    };
  };
  intent: IntentSummary;
  cache_hit: boolean;
}

export interface OllamaModel {
  name: string;
  model: string;
  size: number;
  modified_at: string;
  digest: string;
}

export interface IntentCatalogEntry {
  intent_id: string;
  bpa_domain_intent: string;
  intent_type: string;
  group: string;
  description: string;
  tables?: string[];
  core_fields?: string[];
  nl_examples: string[];
  example_sqls?: string[];
  sql_template: string;
  is_template: boolean;
  generation_strategy: 'template' | 'small_llm' | 'large_llm';
  llm_model?: string;
}

export interface NL2SqlPhaseResult {
  phase: string;
  duration_ms: number;
  success: boolean;
  error?: string;
}

export interface NL2SqlIntentMatch {
  intent_id: string;
  score: number;
  generation_strategy: 'template' | 'small_llm' | 'large_llm';
  sql_template: string;
  tables: string[];
  core_fields: string[];
  description: string;
  intent_type: string;
  group: string;
  nl_examples: string[];
  example_sqls: string[];
}

export interface NL2SqlQueryPlan {
  intent_type: string;
  primary_table: string;
  tables: string[];
  joins: { from_ref: string; to_ref: string; join_type: string }[];
  filters: { field: string; operator: string; value: string }[];
  select_fields: string[];
  aggregations: string[];
  group_by: string[];
  order_by: { field: string; direction: string }[];
  limit: number;
}

export interface NL2SqlValidation {
  is_valid: boolean;
  errors: { layer: number; message: string; severity: string }[];
  warnings: { layer: number; message: string; severity: string }[];
}

export interface NL2SqlExecution {
  sql: string;
  rows: Record<string, unknown>[];
  columns: string[];
  row_count: number;
  execution_time_ms: number;
}

export interface ClarificationQuestion {
  field: string;
  question: string;
}

export interface ClarificationResponse {
  needs_clarification: boolean;
  reason: string;
  questions: ClarificationQuestion[];
}

export interface ErrorExplanation {
  error_type: string;
  explanation: string;
  suggestions: string[];
}

export interface NL2SqlResponse {
  success: boolean;
  query: string;
  matched_intent?: NL2SqlIntentMatch;
  query_plan?: NL2SqlQueryPlan;
  generated_sql: string;
  validation?: NL2SqlValidation;
  execution_result?: NL2SqlExecution;
  clarification?: ClarificationResponse;
  error_explanation?: ErrorExplanation;
  error?: string;
  phases: NL2SqlPhaseResult[];
  total_time_ms: number;
}

export interface RagicImportResult {
  account: string;
  tables_parsed: number;
  schemas_vectorized: number;
  intents_generated: number;
  relations_extracted: number;
  arango_tables_written: number;
  arango_fields_written: number;
  arango_relations_written: number;
  errors: string[];
  duration_ms: number;
}

export interface RagicGraphRelation {
  target_table: string;
  target_field: string;
  source_field: string;
  source_field_id: string;
  relation_type: string;
  direction: string;
}

export interface RagicGraphQueryResult {
  table: string;
  relations: RagicGraphRelation[];
  depth: number;
}

export interface RagicStepResult {
  step_index: number;
  table_key: string;
  table_name: string;
  query_params: Record<string, unknown>;
  records: Record<string, unknown>[];
  record_count: number;
  execution_time_ms: number;
  error: string | null;
}

export interface RagicMultiStepResult {
  query: string;
  steps: RagicStepResult[];
  merged_records: Record<string, unknown>[];
  total_steps: number;
  total_records: number;
  total_time_ms: number;
  partial_failure: boolean;
  errors: string[];
}

export interface RagicIntentItem {
  intent_id: string;
  account: string;
  description: string;
  action: string;
  table_key: string;
  nl_patterns: string[];
  api_template: string;
}

// ---------------------------------------------------------------------------
// NL → Ragic Query (POST /api/v1/da/ragic/query) — Standard Response Protocol
// ---------------------------------------------------------------------------

export interface RagicNLQueryOptions {
  include_subtables?: boolean;
  limit?: number;
  auto_paginate?: boolean;
}

export interface RagicNLQueryRequest {
  query: string;
  connection_name?: string;
  table_key?: string;
  output_format?: 'json' | 'csv' | 'excel';
  options?: RagicNLQueryOptions;
}

export interface RagicNLWhereClause {
  field_id: string;
  operator: 'eq' | 'like' | 'gte' | 'lte' | 'gt' | 'lt' | 'regex';
  value: string;
}

export interface RagicNLTranslatedParams {
  where: RagicNLWhereClause[];
  limit: number;
  offset: number;
  naming?: string;
  order_field?: string | null;
  order_direction?: string;
}

export interface RagicNLRecord {
  ragic_id: string;
  fields: Record<string, unknown>;
}

export interface RagicNLPagination {
  offset: number;
  limit: number;
  returned_count: number;
  has_more: boolean;
}

export interface RagicNLClarification {
  message: string;
  suggestions: string[];
}

export interface RagicNLResultStats {
  total_fields: number;
  estimated_tokens: number;
}

export interface RagicNLResultSet {
  records: RagicNLRecord[];
  record_count: number;
  pagination: RagicNLPagination;
  field_labels: Record<string, string>;
  execution_time_ms: number;
  stats: RagicNLResultStats | null;
}

export interface RagicNLIntentMatch {
  intent_id: string;
  score: number;
  confidence: string;
  action: string;
  table_key: string;
}

export interface RagicNLPostError {
  error_code: number;
  raw_error: string;
  message: string;
}

export interface RagicNLQueryMetadata {
  connection: string;
  table_key: string;
  output_format: string;
  query: string;
  translated_params: RagicNLTranslatedParams | null;
  path_used?: string;
}

export interface RagicNLQueryResponse {
  code: number;
  status: 'success' | 'clarification_needed' | 'error';
  clarification: RagicNLClarification | null;
  result: RagicNLResultSet | null;
  intent: RagicNLIntentMatch | null;
  post_error: RagicNLPostError | null;
  metadata: RagicNLQueryMetadata | null;
}

// ---------------------------------------------------------------------------
// FK Edge Info — describes an expandable FK edge from a record
// ---------------------------------------------------------------------------

export interface FkEdgeInfo {
  from_field_id: string;
  from_field_name: string;
  from_field_value: string;
  target_table_key: string;
  target_table_name: string;
  relation_type: string;
}

export interface FkPreviewResponse {
  record: Record<string, unknown> | null;
  table_name: string;
  fk_edges: FkEdgeInfo[];
}

export interface FkEdgeNode {
  table_key: string;
  table_name: string;
  ragic_id: string;
  fields: Record<string, unknown>;
}

export interface FkEdgeResponse {
  nodes: FkEdgeNode[];
  fk_previews: Record<string, FkEdgeInfo[]>;
  relation_type: string;
  via_field_name: string;
}

// ---------------------------------------------------------------------------
// Record Trace / Lineage (POST /api/v1/da/trace/record)
// ---------------------------------------------------------------------------

export interface RecordTraceNode {
  table_key: string;
  table_name: string;
  ragic_id: string;
  fields: Record<string, unknown>;
  depth: number;
}

export interface RecordTraceEdge {
  from_ragic_id: string;
  from_table_key: string;
  to_ragic_id: string;
  to_table_key: string;
  via_field_id: string;
  via_field_name: string;
  relation_type: string;
}

export interface RecordTraceResponse {
  nodes: RecordTraceNode[];
  edges: RecordTraceEdge[];
  root_ragic_id: string;
  root_table_key: string;
  total_records: number;
  total_time_ms: number;
}
