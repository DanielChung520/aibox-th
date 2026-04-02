/**
 * @file        Data Agent API 服務層 - 型別定義
 * @description DA 的 Schema、Intents、Query 等型別介面定義
 * @lastUpdate  2026-03-24 16:36:01
 * @author      Daniel Chung
 */

export interface TableInfo {
  table_id: string;
  table_name: string;
  module: string;
  description: string;
  s3_path: string;
  primary_keys: string[];
  partition_keys: string[];
  row_count_estimate?: number;
  record_count?: number;
  status: 'enabled' | 'disabled' | 'deprecated';
  version: number;
  created_at: string;
  updated_at: string;
  data_source?: 'sap' | 'ragic';
  tab?: string;
  sheet_key?: string;
}

export interface FieldInfo {
  table_id: string;
  field_id: string;
  field_name: string;
  field_type: string;
  length?: number;
  scale?: number;
  nullable: boolean;
  description: string;
  business_aliases?: string[];
  is_pk: boolean;
  is_fk: boolean;
  relation_table?: string;
  relation_field?: string;
  status: string;
  writable?: boolean;
  is_subtable_field?: boolean;
  subtable_key?: string;
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
