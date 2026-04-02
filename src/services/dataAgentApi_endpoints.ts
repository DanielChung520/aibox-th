/**
 * @file        Data Agent API 服務層 - API 端點函式
 * @description DA 的 Schema、Intents、Query 等 API 端點定義
 * @lastUpdate  2026-03-24 16:36:01
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
};
