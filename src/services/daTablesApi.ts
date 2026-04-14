/**
 * @file        Data Agent Tables & Intents API 服務層
 * @description da_tables / da_intents CRUD 接口
 * @lastUpdate  2026-04-13 12:00:00
 * @author      Daniel Chung
 * @version     2.0.0
 */

import api from './api';

// ============================================================================
// DaIntent 三層架構介面（感知層 / 對策層 / 學習層）
// ============================================================================

export interface DaIntentCapabilities {
  simple_filter: boolean;
  aggregate: boolean;
}

export interface DaIntent {
  _key?: string;
  _id?: string;
  intent_id: string;           // 唯一識別碼 (如 "FORMS4_2_default")
  agent_scope: string;         // 通常是 "data_agent"
  name: string;                // 意圖名稱 (如 "潛在交易對象查詢")
  description?: string;        // 描述

  // 感知層
  nl_examples: string[];       // 場景範例池
  action: 'query' | 'count' | 'sum' | 'update';
  domain: string;              // 業務領域 (sales/crm/contract/inventory/finance)

  // 對策層
  table_key: string;           // 目標表 (如 "FORMS4_2")
  query_type: 'simple_filter' | 'aggregate';
  capabilities: DaIntentCapabilities;

  // 學習層 (可選)
  expected_output?: Record<string, unknown>;
  golden_sql?: string;
  user_feedback_score?: number;
  difficulty_level?: 'easy' | 'medium' | 'hard';

  // 中介層
  is_template?: boolean;

  // 時間戳
  created_at?: string;
  updated_at?: string;
}

export interface DaIntentListParams {
  page?: number;
  page_size?: number;
  table_key?: string;          // 按 table_key 過濾
  intent_type?: string;       // 過濾意圖類型
  group?: string;             // 過濾群組
  generation_strategy?: string;
  search?: string;
}

// ============================================================================
// DaTable 介面（維持不變）
// ============================================================================

export interface DaTableField {
  field_id: string;
  name: string;
  type: string;
  semantic_type?: string | null;
  filterable: boolean;
  aggregatable: boolean;
  aliases: string[];
}

export interface DaTableRelationship {
  target_table: string;
  join_keys: { source_field: string; target_field: string }[];
  cardinality: string;
}

export interface DaTableCapabilities {
  simple_filter: boolean;
  aggregate: boolean;
  time_series: boolean;
  cross_table: boolean;
}

export interface DaTable {
  _key: string;
  display_name: string;
  description: string;
  domain: string;
  status: 'enabled' | 'disabled';
  identifiers: {
    primary: string;
    source: string;
    aliases: string[];
  };
  source_meta: Record<string, unknown>;
  capabilities: DaTableCapabilities;
  fields: DaTableField[];
  relationships: DaTableRelationship[];
  created_at?: string;
  updated_at?: string;
}

export interface DaExpression {
  _key: string;
  table_key: string;
  angle: string;
  name: string;
  description: string;
  aliases: string[];
  nl_examples: string[];
  status: 'enabled' | 'disabled';

  // 感知層
  action: 'query' | 'count' | 'sum' | 'update';
  domain: string;

  // 對策層
  query_type: 'simple_filter' | 'aggregate';
  tool_schema?: Record<string, unknown>;
  capabilities?: Record<string, boolean>;

  // 學習層
  expected_output?: Record<string, unknown>;
  golden_sql?: string;
  user_feedback_score?: number;
  difficulty_level?: 'easy' | 'medium' | 'hard';

  // 中介層
  is_template?: boolean;

  created_at?: string;
  updated_at?: string;
}

interface PaginatedResponse<T> {
  code: number;
  data: {
    records: T[];
    total: number;
    page: number;
    page_size: number;
  };
}

interface SingleResponse<T> {
  code: number;
  message: string;
  data: T;
}

export interface DaTableListParams {
  page?: number;
  page_size?: number;
  domain?: string;
  status?: string;
  search?: string;
}

export interface DaExpressionListParams {
  page?: number;
  page_size?: number;
  table_key?: string;
  status?: string;
  search?: string;
}

export const daTablesApi = {
  list: (params: DaTableListParams) =>
    api.get<PaginatedResponse<DaTable>>('/api/v1/da/tables', { params }),

  get: (key: string) =>
    api.get<SingleResponse<DaTable>>(`/api/v1/da/tables/${key}`),

  create: (data: Partial<DaTable>) =>
    api.post<SingleResponse<DaTable>>('/api/v1/da/tables', data),

  update: (key: string, data: Partial<DaTable>) =>
    api.put<SingleResponse<DaTable>>(`/api/v1/da/tables/${key}`, data),

  delete: (key: string) =>
    api.delete(`/api/v1/da/tables/${key}`),
};

export const daIntentsApi = {
  list: (params: DaIntentListParams) =>
    api.get<PaginatedResponse<DaIntent>>('/api/v1/da/intents/catalog', { params }),

  get: (intentId: string) =>
    api.get<SingleResponse<DaIntent>>(`/api/v1/da/intents/catalog/${intentId}`),

  create: (data: Partial<DaIntent>) =>
    api.post<SingleResponse<DaIntent>>('/api/v1/da/intents/catalog', data),

  update: (intentId: string, data: Partial<DaIntent>) =>
    api.put<SingleResponse<DaIntent>>(`/api/v1/da/intents/catalog/${intentId}`, data),

  delete: (intentId: string) =>
    api.delete(`/api/v1/da/intents/catalog/${intentId}`),

  feedback: (intentId: string, action: string, nlQuery: string) =>
    api.post<{ action: string; intent_id: string; applied: boolean }>(
      `/api/v1/da/intents/catalog/${intentId}/feedback`,
      { action, nl_query: nlQuery }
    ),

  syncToQdrant: () =>
    api.post<{ synced_count: number; collection: string; status: string }>(
      '/api/v1/da/intents/sync-qdrant', {}
    ),

  listModels: () =>
    api.get<{ models: string[] }>('/api/v1/da/intents/models'),
};

// ============================================================================
// daExpressionsApi (Legacy - 即将废弃，改用 daIntentsApi)
// ============================================================================

export const daExpressionsApi = {
  list: (params: DaExpressionListParams) =>
    api.get<PaginatedResponse<DaExpression>>('/api/v1/da/expressions', { params }),

  get: (key: string) =>
    api.get<SingleResponse<DaExpression>>(`/api/v1/da/expressions/${key}`),

  create: (data: Partial<DaExpression>) =>
    api.post<SingleResponse<DaExpression>>('/api/v1/da/expressions', data),

  update: (key: string, data: Partial<DaExpression>) =>
    api.put<SingleResponse<DaExpression>>(`/api/v1/da/expressions/${key}`, data),

  delete: (key: string) =>
    api.delete(`/api/v1/da/expressions/${key}`),

  syncToQdrant: () =>
    api.post<{ synced_count: number; collection: string; status: string }>(
      '/api/v1/da/expressions/sync-qdrant', {}
    ),
};
