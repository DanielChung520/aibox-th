/**
 * @file        Unified Intent Catalog API 服務層
 * @description 統一意圖目錄 CRUD 接口，以 agent_scope 區分 orchestrator / data_agent
 * @lastUpdate  2026-04-13 03:37:18
 * @author      Daniel Chung
 * @version     1.4.0
 */

import api from './api';

// ==================== Types ====================

export type AgentScope = 'orchestrator' | 'data_agent';

export interface IntentCatalogEntry {
  _key?: string;
  intent_id: string;
  agent_scope: AgentScope;
  name: string;
  description: string;
  nl_examples: string[];
  status: 'enabled' | 'disabled';
  priority: number;
  created_at?: string;
  updated_at?: string;
  updated_by?: string;

  // ── Orchestrator (BPA routing model) ──
  intent_type?: string;
  domain?: string;
  bpa_id?: string;
  task_type?: 'query' | 'action' | 'workflow';
  capabilities?: string[];
  confidence_threshold?: number;
  response_strategy?: 'direct_llm' | 'confirm_then_execute' | 'clarify_first' | 'handoff_bpa';

  // ── DataAgent (NL→SQL model) ──
  table_id?: string;
  sheet_key?: string;
  group?: string;
  tables?: string[];
  generation_strategy?: 'template' | 'small_llm' | 'large_llm';
  sql_template?: string;
  core_fields?: string[];
  example_sqls?: string[];
  bpa_domain_intent?: string;
  table_key?: string;
  action?: string;
  nl_patterns?: string[];

  // ── B+C 混合架構擴充（兩階段意圖路由） ──
  query_type?: 'simple_filter' | 'aggregate' | 'cross_table' | 'time_series';
  tool_schema?: Record<string, unknown>;
  involved_tables?: string[];
  join_keys?: Record<string, unknown>[];
  expected_output?: Record<string, unknown>;
  difficulty_level?: 'easy' | 'medium' | 'hard';
  golden_sql?: string;
  test_cases?: Record<string, unknown>[];
}

export interface IntentCatalogListResponse {
  code: number;
  data: {
    records: IntentCatalogEntry[];
    total: number;
    page: number;
    page_size: number;
  };
}

export interface IntentCatalogListParams {
  agent_scope: AgentScope;
  page?: number;
  page_size?: number;
  status?: string;
  intent_type?: string;
  search?: string;
  tool_name?: string;
  group?: string;
  generation_strategy?: string;
  response_strategy?: string;
  query_type?: string;
}

// ==================== API ====================

export const intentCatalogApi = {
  list: (params: IntentCatalogListParams) =>
    api.get<IntentCatalogListResponse>('/api/v1/intents/catalog', { params }),

  create: (data: Partial<IntentCatalogEntry>) =>
    api.post<{ code: number; data: IntentCatalogEntry }>('/api/v1/intents/catalog', data),

  update: (intentId: string, data: Partial<IntentCatalogEntry>) =>
    api.put<{ code: number; data: IntentCatalogEntry }>(`/api/v1/intents/catalog/${intentId}`, data),

  delete: (intentId: string) =>
    api.delete(`/api/v1/intents/catalog/${intentId}`),

  feedback: (intentId: string, data: { action: 'thumbs_up' | 'thumbs_down'; nl_query: string }) =>
    api.post<{ code: number; data: { action: string; intent_id: string; applied: boolean; nl_added?: string } }>(
      `/api/v1/intents/catalog/${intentId}/feedback`, data
    ),

  syncToQdrant: (data: { agent_scope: AgentScope; model?: string }) =>
    api.post<{ synced_count: number; collection: string; status: string }>(
      '/api/v1/intents/sync-qdrant', data
    ),

  listModels: (agentScope: AgentScope) =>
    api.get<{ models: string[] }>('/api/v1/intents/models', { params: { agent_scope: agentScope } }),
};

export default intentCatalogApi;
