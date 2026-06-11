/**
 * @file        intentLogApi.ts
 * @description 意圖日誌 API 服務層 — 記錄使用者與意圖猜測的互動
 * @lastUpdate  2026-04-16 20:34:33
 * @author      Daniel Chung
 * @version     1.0.0
 */

import api from './api';

export type IntentLogAction = 'confirmed' | 'modified' | 'rejected' | 'ignored' | 'clarified';

export interface IntentLog {
  _key?: string;
  intent_id?: string;
  user_id?: string;
  action: IntentLogAction;
  page_path: string;
  page_type?: string;
  original_text: string;
  final_text?: string;
  confidence: number;
  source: 'template' | 'rule' | 'llm';
  created_at?: string;
}

export interface IntentLogListResponse {
  code: number;
  data: {
    records: IntentLog[];
    total: number;
    page: number;
    page_size: number;
  };
}

export interface IntentLogListParams {
  intent_id?: string;
  user_id?: string;
  action?: IntentLogAction;
  page_type?: string;
  page?: number;
  page_size?: number;
}

export interface IntentLogStat {
  action: string;
  count: number;
}

export const intentLogApi = {
  create: (data: Omit<IntentLog, '_key' | 'created_at'>) =>
    api.post<{ code: number; data: string }>('/api/v1/intent-logs', data),

  list: (params: IntentLogListParams) =>
    api.get<IntentLogListResponse>('/api/v1/intent-logs', { params }),

  stats: (intentId?: string) =>
    api.get<{ code: number; data: IntentLogStat[] }>('/api/v1/intent-logs/stats', {
      params: intentId ? { intent_id: intentId } : {},
    }),
};

export default intentLogApi;
