/**
 * @file        Data Agent API 服務層 - API 端點函式
 * @description DA 的 Schema、Intents、Query 等 API 端點定義
 * @lastUpdate  2026-05-01 10:31:57
 * @author      Daniel Chung
 */

import api from './api';
import type {
  TableInfo,
  FieldInfo,
  TableRelation,
  QueryRequest,
  QueryResponse,
  IntentCatalogEntry,
  NL2SqlResponse,
  RagicImportResult,
  RagicGraphQueryResult,
  RagicMultiStepResult,
  RagicIntentItem,
  RagicNLQueryRequest,
  RagicNLQueryResponse,
  RecordTraceResponse,
  FkPreviewResponse,
  FkEdgeResponse,
} from './dataAgentApi_types';

export const dataAgentApi_endpoints = {
  // Schema - Tables
  listTables: () => api.get<{ code: number; data: TableInfo[] }>('/api/v1/da/schema/tables'),

  getTable: (tableId: string) =>
    api.get<{ code: number; data: TableInfo }>(`/api/v1/da/schema/tables/${tableId}`),

  createTable: (data: Partial<TableInfo>) =>
    api.post('/api/v1/da/schema/tables', data),

  updateTable: (tableId: string, data: Partial<TableInfo>) =>
    api.put(`/api/v1/da/schema/tables/${tableId}`, data),

  deleteTable: (tableId: string) =>
    api.delete(`/api/v1/da/schema/tables/${tableId}`),

  // Schema - Fields
  listFields: (tableId: string) =>
    api.get<{ code: number; data: FieldInfo[] }>(`/api/v1/da/schema/tables/${tableId}/fields`),

  createField: (data: Partial<FieldInfo>) =>
    api.post(`/api/v1/da/schema/tables/${data.table_id}/fields`, data),

  updateField: (tableId: string, fieldId: string, data: Partial<FieldInfo>) =>
    api.put(`/api/v1/da/schema/tables/${tableId}/fields/${fieldId}`, data),

  deleteField: (tableId: string, fieldId: string) =>
    api.delete(`/api/v1/da/schema/tables/${tableId}/fields/${fieldId}`),

  // Schema - Relations
  listRelations: () =>
    api.get<{ code: number; data: TableRelation[] }>('/api/v1/da/schema/relations'),

  createRelation: (data: Partial<TableRelation>) =>
    api.post('/api/v1/da/schema/relations', data),

  updateRelation: (relationId: string, data: Partial<TableRelation>) =>
    api.put(`/api/v1/da/schema/relations/${relationId}`, data),

  deleteRelation: (relationId: string) =>
    api.delete(`/api/v1/da/schema/relations/${relationId}`),

  // Intents
  listCatalog: (params?: {
    page?: number;
    page_size?: number;
    group?: string;
    intent_type?: string;
    search?: string;
    generation_strategy?: string;
  }) =>
    api.get<{
      code: number;
      data: { records: IntentCatalogEntry[]; total: number; page: number; page_size: number };
    }>('/api/v1/da/intents/catalog', { params }),

  createIntent: (data: IntentCatalogEntry) =>
    api.post('/api/v1/da/intents/catalog', data),

  updateIntent: (intentId: string, data: IntentCatalogEntry) =>
    api.put(`/api/v1/da/intents/catalog/${intentId}`, data),

  deleteIntent: (intentId: string) =>
    api.delete(`/api/v1/da/intents/catalog/${intentId}`),

  feedbackIntent: (
    intentId: string,
    data: { action: 'thumbs_up' | 'thumbs_down'; nl_query: string }
  ) =>
    api.post<{ code: number; data: { action: string; intent_id: string; applied: boolean; nl_added?: string } }>(
      `/api/v1/da/intents/catalog/${intentId}/feedback`,
      data
    ),

  syncToQdrant: (data: { model?: string }) => {
    return api.post<{ synced_count: number }>('/api/v1/da/intents/sync-qdrant', data);
  },

  // Query
  query: (data: QueryRequest) => {
    return api.post<QueryResponse>('/api/v1/da/query', data);
  },

  // NL→SQL Pipeline
  nl2sql: (data: { natural_language: string }) => {
    return api.post<NL2SqlResponse>('/api/v1/da/query/nl2sql', data, { timeout: 180000 });
  },

  querySql: (data: { sql: string; params?: unknown[] }) => {
    return api.post<{ code: number; data: unknown }>('/api/v1/da/query/sql', data);
  },

  // Sync
  getSyncStatus: () => {
    return api.get<{ code: number; data: unknown }>('/api/v1/da/sync/status');
  },

  triggerSync: () => {
    return api.post<{ code: number; data: unknown }>('/api/v1/da/sync/trigger');
  },

  // Health
  health: () => api.get<{ status: string }>('/api/v1/da/health'),

  // Data Lake Preview
  previewTable: (tableName: string, offset = 0, limit = 20) =>
    api.get<{
      code: number;
      table_name: string;
      table_id: string;
      table_info: TableInfo;
      fields: FieldInfo[];
      rows: Record<string, unknown>[];
      total: number;
      offset: number;
      limit: number;
    }>(`/api/v1/da/query/tables/${tableName}/preview`, { params: { offset, limit } }),

  // Ragic API Proxy
  ragicProxyData: (tableId: string, offset = 0, limit = 20) =>
    api.get<{
      code: number;
      message?: string;
      table_id: string;
      table_name: string;
      fields: FieldInfo[];
      rows: Record<string, unknown>[];
      total: number;
      offset: number;
      limit: number;
    }>(`/api/v1/da/ragic/proxy/${tableId}/data`, { params: { offset, limit } }),

  ragicCacheRefresh: (tableId: string) =>
    api.post<{ code: number; data: { table_id: string; row_count: number; cached_at: string } }>(
      `/api/v1/da/ragic/cache/${tableId}/refresh`
    ),

  ragicCacheMeta: (tableId: string) =>
    api.get<{ code: number; data: { table_id: string; row_count: number; cached_at: string } | null }>(
      `/api/v1/da/ragic/cache/${tableId}/meta`
    ),

  importRagicMd: (data: { account: string; content: string }) =>
    api.post<{ code: number; message: string; data: RagicImportResult | null }>(
      '/api/v1/da/ragic/schema/import-md', data, { timeout: 300000 }
    ),

  ragicRelatedTables: (tableName: string, account: string, depth?: number) =>
    api.get<{ code: number; data: RagicGraphQueryResult | null }>(
      '/api/v1/da/ragic/graph/related-tables', { params: { table_name: tableName, account, depth } }
    ),

  ragicGraphPath: (fromTable: string, toTable: string, account: string) =>
    api.get<{ code: number; data: Record<string, unknown>[] | null }>(
      '/api/v1/da/ragic/graph/path', { params: { from_table: fromTable, to_table: toTable, account } }
    ),

  ragicAllRelations: (account: string) =>
    api.get<{ code: number; data: Record<string, unknown>[] }>(
      '/api/v1/da/ragic/graph/all-relations', { params: { account } }
    ),

  ragicMultiStepQuery: (data: { query: string; account: string; max_steps?: number }) =>
    api.post<{ code: number; data: RagicMultiStepResult | null; error: string | null }>(
      '/api/v1/da/ragic/query/multi-step', data, { timeout: 120000 }
    ),

  listRagicIntents: (account: string, limit = 500) =>
    api.get<{ code: number; data: RagicIntentItem[]; total: number }>(
      '/api/v1/da/ragic/intents', { params: { account, limit } }
    ),

  ragicNLQuery: (data: RagicNLQueryRequest) =>
    api.post<RagicNLQueryResponse>('/api/v1/da/ragic/query', data, { timeout: 120000 }),

  // Trace — Record Data Lineage
  recordTrace: (data: { table_key: string; record_id: string; account: string; depth?: number }) =>
    api.post<{ code: number; data: RecordTraceResponse }>(
      '/api/v1/da/trace/record', data, { timeout: 120000 }
    ),

  // Progressive lineage — FK preview (root record + ghost edges, no traversal)
  fkPreview: (data: { table_key: string; record_id: string; account: string }) =>
    api.post<{ code: number; data: FkPreviewResponse }>(
      '/api/v1/da/trace/fk-preview', data, { timeout: 15000 }
    ),

  // Progressive lineage — expand a single FK edge
  fkExpandEdge: (data: {
    table_key: string; record_id: string;
    field_id: string; field_value: string;
    account: string; via_field_name?: string;
  }) => api.post<{ code: number; data: FkEdgeResponse }>(
    '/api/v1/da/trace/fk-edge', data, { timeout: 30000 }
  ),

  runTraceScenario: (scenarioId: string, data: {
    entry_batch?: string; entry_table?: string;
    depth?: number; max_fan_out?: number;
    options?: Record<string, unknown>;
  }) => api.post<{ code: number; data: unknown }>(
    `/api/v1/da/trace-engine/scenario/${scenarioId}`, data, { timeout: 180000 }
  ),

  nlParseTrace: (data: { text: string }) =>
    api.post<{ code: number; data: { parsed: boolean; scenario: string | null; batch_no: string; suggestion: string } }>(
      '/api/v1/da/trace-engine/nl-parse', data, { timeout: 15000 }
    ),

  saveTraceReport: (data: {
    name: string; scenario: string;
    entry_table?: string; entry_batch?: string;
    trace_result?: Record<string, unknown> | null;
    summary?: Record<string, unknown>;
    tags?: string[]; created_by?: string;
  }) => api.post<{ code: number; data: { key: string } }>(
    '/api/v1/da/trace-engine/report/save', data, { timeout: 15000 }
  ),

  getTraceReport: (reportId: string) =>
    api.get<{ code: number; data: Record<string, unknown> }>(
      `/api/v1/da/trace-engine/report/${reportId}`
    ),

  listTraceReports: (params?: { scenario?: string; page?: number; limit?: number }) =>
    api.get<{ code: number; data: Record<string, unknown>[]; page: number; limit: number }>(
      '/api/v1/da/trace-engine/reports', { params }
    ),

  deleteTraceReport: (reportId: string) =>
    api.delete<{ code: number; message: string }>(
      `/api/v1/da/trace-engine/report/${reportId}`
    ),

  traceEngineHealth: () =>
    api.get<{ status: string; service: string }>(
      '/api/v1/da/trace-engine/health'
    ),
};
